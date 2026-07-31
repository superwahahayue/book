import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', name: 'library', component: () => import('@/views/LibraryView.vue') },
  { path: '/create', name: 'create', component: () => import('@/views/CreateView.vue') },
  { path: '/novels/:id', name: 'novel', component: () => import('@/views/NovelView.vue'), props: true },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

export default router
