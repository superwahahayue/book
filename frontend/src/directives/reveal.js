// v-reveal: fade+rise an element into view as it enters the viewport.
// Optional value = stagger delay in ms.
const io = new IntersectionObserver(
  (entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible')
        io.unobserve(entry.target)
      }
    }
  },
  { threshold: 0.08, rootMargin: '0px 0px -40px 0px' }
)

export default {
  mounted(el, binding) {
    el.classList.add('reveal')
    if (binding.value) el.style.transitionDelay = `${binding.value}ms`
    io.observe(el)
  },
  unmounted(el) {
    io.unobserve(el)
  },
}
