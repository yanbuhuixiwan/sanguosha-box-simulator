import { ref } from 'vue'

const list = ref([])
let seq = 0

function push(message, type = 'info', ttl = 2600) {
  const id = ++seq
  list.value.push({ id, message, type })
  setTimeout(() => {
    list.value = list.value.filter((t) => t.id !== id)
  }, ttl)
}

export function useToast() {
  return {
    toasts: list,
    toast: push,
    error: (m) => push(m, 'error', 3200),
    success: (m) => push(m, 'success', 2600),
  }
}
