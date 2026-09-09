import { createRouter, createWebHistory } from 'vue-router'
import { auth, loadCurrentUser } from '@/auth'

const routes = [
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { guestOnly: true } },
  { path: '/register', name: 'register', component: () => import('@/views/RegisterView.vue'), meta: { guestOnly: true } },
  { path: '/', name: 'library', component: () => import('@/views/LibraryView.vue'), meta: { requiresAuth: true } },
  { path: '/create', name: 'create', component: () => import('@/views/CreateView.vue'), meta: { requiresAuth: true } },
  { path: '/import', name: 'import-novel', component: () => import('@/views/ImportNovelView.vue'), meta: { requiresAuth: true } },
  { path: '/novels/:id', name: 'novel', component: () => import('@/views/NovelView.vue'), props: true, meta: { requiresAuth: true } },
  {
    path: '/novels/:novelId/chapters/:chapterId/comic',
    name: 'comic',
    component: () => import('@/views/ComicView.vue'),
    props: (route) => ({
      novelId: route.params.novelId,
      chapterId: route.params.chapterId,
      comicId: route.query.comic || null,
    }),
    meta: { requiresAuth: true },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})

router.beforeEach(async (to) => {
  if (!auth.loaded) await loadCurrentUser()
  if (to.meta.requiresAuth && !auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (to.meta.guestOnly && auth.user) return { name: 'library' }
  return true
})

export default router
