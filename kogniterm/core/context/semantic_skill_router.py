"""
semantic_skill_router.py — Enrutador Semántico de Skills Procedimentales

Dado el mensaje del usuario, selecciona las skills procedimentales más
relevantes por similitud semántica (embeddings + scoring léxico) y devuelve
un bloque de texto listo para inyectar en el system prompt.

Se apoya en la infraestructura existente de `SkillManager`:
- `find_relevant_skills(query, limit)` -> ranking semántico
- `get_skill_instructions(name)` -> cuerpo Markdown de la skill

A diferencia de `build_skill_context_message` (que solo mira skills ya
cargadas), este router puede descubrir skills NO cargadas que sean relevantes
y recuperar sus instrucciones completas, evitando que el agente tenga que
adivinar el nombre vía `#skill`.

Filtrado defensivo: `find_relevant_skills` puede inflar el score de skills con
instrucciones muy largas (muchos tokens genéricos coinciden). Este router
aplica un filtro adicional por nombre/tag para evitar ruido y limita el tamaño
total del bloque para no reventar el context window.
"""

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Score mínimo para considerar una skill candidata (find_relevant_skills
# devuelve scores que combinan coseno*10 con bonuses léxicos).
_MIN_SCORE = 3.0
# Score a partir del cual se acepta la skill aunque no haya overlap léxico
# de nombre (similitud semántica fuerte vía embeddings).
_STRONG_SEMANTIC_SCORE = 12.0
# Similitud coseno mínima para aceptar una skill sin overlap léxico.
_MIN_COSINE = 0.55

# Boost explícito: si la query contiene alguno de estos keywords, se fuerza la
# inclusión de la skill asociada (bypass total del scoring semántico). Útil
# para casos cross-idioma o de dominio específico donde el embedding genérico
# no es suficientemente discriminativo.
_KEYWORD_SKILL_BOOST = {
    "user-context": [
        "contexto global", "perfil de usuario", "perfil del usuario",
        "mi nombre", "me llamo", "mis preferencias", "mis proyectos",
        "recuérdame", "recuerdame", "guarda mi", "guardar mi",
        "user context", "user profile", "global context",
    ],
    "memory-append": [
        "memoria del proyecto", "guarda en memoria", "guardar en memoria",
        "memoria contextual", "llm_context",
    ],
}
# Límite de skills a inyectar.
_MAX_SKILLS = 3
# Tope de caracteres por skill (evita que una skill gigante domine el prompt).
_MAX_CHARS_PER_SKILL = 3500
# Tope de caracteres TOTALES del bloque de skills.
_MAX_TOTAL_CHARS = 9000

# Palabras vacías en español/inglés para el filtro de coincidencia de nombre.
_STOPWORDS = {
    "de", "la", "el", "en", "y", "a", "los", "del", "las", "un", "una", "por",
    "con", "no", "si", "como", "para", "es", "al", "lo", "pero", "sus", "le",
    "ya", "o", "porque", "esta", "este", "eso", "the", "a", "an", "and", "or",
    "of", "to", "in", "is", "it", "for", "on", "with", "as", "at", "by", "que",
    "mi", "tu", "su", "yo", "tu", "me", "te", "se", "nos", "les", "un", "una",
}


class SemanticSkillRouter:
    """Selecciona e inyecta skills procedimentales relevantes por semántica."""

    def __init__(self, skill_manager: Any) -> None:
        self.skill_manager = skill_manager

    def route(self, query: str, limit: int = _MAX_SKILLS) -> List[Dict[str, Any]]:
        """Devuelve las skills relevantes para la query con sus instrucciones.

        Estrategia de filtrado (en capas):
        1. Obtener candidatos de `find_relevant_skills` (amplio).
        2. Calcular la similitud coseno REAL entre el embedding de la query y el
           de cada skill (evita que skills con instrucciones largas inflen el
           score por tokens genéricos).
        3. Exigir overlap léxico de nombre/tag/descripción O cosine alta.
        4. Ordenar por score combinado y limitar.

        Returns:
            Lista de dicts: {name, description, score, instructions}
        """
        if not query or not query.strip() or not self.skill_manager:
            return []

        try:
            relevant = self.skill_manager.find_relevant_skills(
                query=query,
                limit=max(limit * 4, 12),
                include_unloaded=True,
            )
        except Exception as e:
            logger.warning("SemanticSkillRouter: error en find_relevant_skills: %s", e)
            return []

        query_tokens = self._tokenize(query)
        query_embedding = self._embed_query(query)
        query_lower = query.lower()

        # Skills forzadas por keyword (bypass de scoring)
        forced = set()
        for skill_name, keywords in _KEYWORD_SKILL_BOOST.items():
            if any(kw in query_lower for kw in keywords):
                forced.add(skill_name)

        scored: List[tuple] = []
        for item in relevant:
            raw_score = item.get("score", 0)
            if raw_score < _MIN_SCORE:
                continue

            name = item.get("name", "")
            cosine = self._cosine_with_skill(name, query_embedding)

            # Overlap léxico (nombre/tags/descripción)
            has_overlap = (
                self._has_name_overlap(name, item.get("tags", []), query_tokens)
                or self._has_desc_overlap(item.get("description", ""), query_tokens)
            )

            # Criterio de aceptación:
            # - forzada por keyword, O
            # - overlap léxico con score decente, O
            # - cosine semántica alta (bypass cross-idioma), O
            # - nombre de skill contenido literalmente en la query
            name_in_query = bool(name) and name.lower().replace("-", " ") in query.lower()
            is_forced = name in forced
            accept = (
                is_forced
                or (has_overlap and raw_score >= _MIN_SCORE)
                or cosine >= _MIN_COSINE
                or name_in_query
            )
            if not accept:
                continue

            # Score final: combina cosine (0-1 -> 0-10) con el score crudo.
            # Las forzadas reciben un bonus alto para rankear primero.
            combined = (cosine * 10.0) + (raw_score * 0.3)
            if is_forced:
                combined += 100.0
            scored.append((combined, name, item))

        # Inyectar skills forzadas que no aparecieron entre los candidatos
        # (find_relevant_skills puede omitirlas si su score crudo es bajo).
        already = {name for _, name, _ in scored}
        for skill_name in forced:
            if skill_name in already:
                continue
            skill_obj = getattr(self.skill_manager, "skills", {}).get(skill_name)
            if skill_obj is None:
                continue
            scored.append((
                1000.0,  # prioridad máxima
                skill_name,
                {
                    "name": skill_name,
                    "description": getattr(skill_obj, "description", ""),
                    "category": getattr(skill_obj, "category", ""),
                    "tags": getattr(skill_obj, "tags", []),
                    "score": 1000.0,
                },
            ))

        scored.sort(key=lambda x: -x[0])

        results: List[Dict[str, Any]] = []
        for combined, name, item in scored[:limit]:
            instructions = self._get_instructions(name)
            if not instructions:
                continue
            results.append({
                "name": name,
                "description": item.get("description", ""),
                "category": item.get("category", ""),
                "score": round(combined, 2),
                "instructions": instructions,
            })

        return results

    def _embed_query(self, query: str):
        """Obtiene (o cachea) el embedding de la query."""
        try:
            emb_service = getattr(self.skill_manager, "embeddings_service", None)
            if emb_service:
                return emb_service.embed_query(query)
        except Exception as e:
            logger.debug("SemanticSkillRouter: error embed_query: %s", e)
        return None

    def _cosine_with_skill(self, skill_name: str, query_embedding) -> float:
        """Calcula la similitud coseno entre la query y una skill."""
        if query_embedding is None:
            return 0.0
        try:
            import numpy as np
            skill_vec = getattr(self.skill_manager, "skill_embeddings", {}).get(skill_name)
            if not skill_vec:
                return 0.0
            qv = np.array(query_embedding)
            sv = np.array(skill_vec)
            nq = np.linalg.norm(qv)
            ns = np.linalg.norm(sv)
            if nq <= 0 or ns <= 0:
                return 0.0
            return float(np.dot(qv, sv) / (nq * ns))
        except Exception:
            return 0.0

    @staticmethod
    def _tokenize(text: str) -> set:
        """Extrae tokens significativos (sin stopwords) de un texto."""
        tokens = re.split(r"\W+", (text or "").lower())
        return {t for t in tokens if t and t not in _STOPWORDS and len(t) > 2}

    def _has_name_overlap(self, name: str, tags: List[str], query_tokens: set) -> bool:
        """True si el nombre o tags de la skill comparten tokens con la query."""
        if not query_tokens:
            return False
        # Normalizar nombre: separar por guiones/underscores/espacios
        name_tokens = set(re.split(r"[-_\s]+", (name or "").lower()))
        tag_tokens = set()
        for tag in (tags or []):
            tag_tokens |= set(re.split(r"[-_\s]+", str(tag).lower()))
        skill_tokens = (name_tokens | tag_tokens) - _STOPWORDS
        return bool(skill_tokens & query_tokens)

    def _has_desc_overlap(self, description: str, query_tokens: set) -> bool:
        """True si la descripción de la skill comparte tokens con la query."""
        if not description or not query_tokens:
            return False
        desc_tokens = self._tokenize(description)
        return bool(desc_tokens & query_tokens)

    def _get_instructions(self, skill_name: str) -> Optional[str]:
        """Obtiene las instrucciones de una skill, cargándola si es necesario."""
        try:
            sm = self.skill_manager
            skills_dict = getattr(sm, "skills", {})
            skill_obj = skills_dict.get(skill_name)
            if skill_obj is not None and not getattr(skill_obj, "loaded", False):
                if hasattr(sm, "load_skill"):
                    sm.load_skill(skill_name)

            if hasattr(sm, "get_skill_instructions"):
                instr = sm.get_skill_instructions(skill_name)
                if instr:
                    return instr.strip()

            if skill_obj is not None:
                return (getattr(skill_obj, "instructions", "") or "").strip() or None
        except Exception as e:
            logger.debug("SemanticSkillRouter: no se pudo obtener instrucciones de '%s': %s", skill_name, e)
        return None

    def build_prompt_block(self, query: str) -> str:
        """Construye el bloque de texto a inyectar en el system prompt.

        Devuelve "" si no hay skills relevantes. Limita el tamaño total.
        """
        routed = self.route(query)
        if not routed:
            return ""

        parts = [
            "\n\n## 🧭 SKILLS PROCEDIMENTALES RELEVANTES PARA ESTA CONSULTA",
            "",
            "Las siguientes skills procedimentales han sido seleccionadas "
            "automáticamente por su relevancia semántica con la petición del "
            "usuario. SON GUÍAS DE CONOCIMIENTO EN TEXTO, NO herramientas de "
            "código. Léelas y APLICA sus instrucciones directamente. No intentes "
            "invocarlas como funciones.",
            "",
        ]

        total_len = sum(len(p) for p in parts)
        added_any = False
        for item in routed:
            instr = item["instructions"]
            if len(instr) > _MAX_CHARS_PER_SKILL:
                instr = instr[:_MAX_CHARS_PER_SKILL] + "\n\n[... instrucción truncada por longitud ...]"

            block = (
                f"### SKILL: {item['name']}\n"
                f"- Descripción: {item['description']}\n"
                f"- Relevancia: {item['score']}\n\n"
                f"{instr}\n"
            )

            if total_len + len(block) > _MAX_TOTAL_CHARS:
                break

            parts.append(block)
            total_len += len(block)
            added_any = True

        # Si no se añadió ninguna skill (por límite de tamaño), no inyectar nada.
        if not added_any:
            return ""

        return "\n".join(parts)
