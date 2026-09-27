import * as LRUModule from "../../../../node_modules/lru_map/dist/lru.js"

const LRUMap = (LRUModule as any).LRUMap || (LRUModule as any).default || LRUModule
export { LRUMap }
export default { LRUMap }
