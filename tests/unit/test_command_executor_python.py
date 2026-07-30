import os
import pytest
from kogniterm.core.command_executor import CommandExecutor, _transform_python3_dash_c


def test_transform_python3_dash_c_double_quotes():
    cmd = 'python3 -c "import time; print(\'hello\')"'
    transformed, was_transformed, temp_path = _transform_python3_dash_c(cmd)
    
    assert was_transformed is True
    assert temp_path is not None
    assert "-u" in transformed
    assert temp_path in transformed
    
    # Cleanup temp file
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_transform_python3_dash_c_single_quotes():
    cmd = "python -c 'print(\"test\")'"
    transformed, was_transformed, temp_path = _transform_python3_dash_c(cmd)
    
    assert was_transformed is True
    assert temp_path is not None
    assert "-u" in transformed
    assert temp_path in transformed
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_transform_python3_dash_c_already_has_unbuffered_flag():
    cmd = 'python3 -u -c "print(123)"'
    transformed, was_transformed, temp_path = _transform_python3_dash_c(cmd)
    
    assert was_transformed is True
    assert transformed.count("-u") == 1
    
    if temp_path and os.path.exists(temp_path):
        os.unlink(temp_path)


def test_command_executor_python_execution():
    executor = CommandExecutor()
    cmd = 'python3 -c "import sys; sys.stdout.write(\'out1\\n\'); sys.stdout.flush()"'
    
    chunks = list(executor.execute(cmd))
    output = "".join(chunks)
    
    assert "out1" in output
    assert "##KOGNITERM_DONE_MARKER##" not in output


def test_command_executor_python_multiline():
    executor = CommandExecutor()
    cmd = 'python3 -c "for i in range(3):\n    print(f\'num_{i}\')"'
    
    chunks = list(executor.execute(cmd))
    output = "".join(chunks)
    
    assert "num_0" in output
    assert "num_1" in output
    assert "num_2" in output


def test_transform_python3_dash_c_triple_quotes():
    cmd = 'python3 -c """import sys\nfor i in range(2):\n    print(f"triple_{i}")"""'
    transformed, was_transformed, temp_path = _transform_python3_dash_c(cmd)
    
    assert was_transformed is True
    assert temp_path is not None
    assert "-u" in transformed
    
    with open(temp_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert 'print(f"triple_{i}")' in content
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)


def test_transform_python3_dash_c_no_catastrophic_backtracking():
    import time
    # Comando extenso con múltiples espacios y flags que anteriormente causaba congelamiento por ReDoS
    cmd = "python " + " -v" * 30 + " -c \"print(" + "1 + " * 50 + "1)\""
    
    t0 = time.time()
    transformed, was_transformed, temp_path = _transform_python3_dash_c(cmd)
    t1 = time.time()
    
    # Debe completarse casi instantáneamente (< 0.05 segundos) sin bloquear el hilo
    assert (t1 - t0) < 0.05
    assert was_transformed is True
    assert temp_path is not None
    
    if os.path.exists(temp_path):
        os.unlink(temp_path)

