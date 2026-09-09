import axios from 'axios'

const http = axios.create({
  baseURL: '/api',
  timeout: 120000,
  withCredentials: true,
})

function upload(path, file, fields = {}) {
  const form = new FormData()
  form.append('file', file)
  for (const [key, value] of Object.entries(fields)) {
    if (value !== undefined && value !== null && value !== '') {
      form.append(key, String(value))
    }
  }
  return http.post(path, form).then((r) => r.data)
}

export const api = {
  register: (data) => http.post('/auth/register', data).then((r) => r.data),
  login: (data) => http.post('/auth/login', data).then((r) => r.data),
  logout: () => http.post('/auth/logout'),
  currentUser: () => http.get('/auth/me').then((r) => r.data),
  listProviders: () => http.get('/providers').then((r) => r.data),
  listNovels: () => http.get('/novels').then((r) => r.data),
  getNovel: (id) => http.get(`/novels/${id}`).then((r) => r.data),
  createNovel: (data) => http.post('/novels', data).then((r) => r.data),
  updateNovel: (id, data) => http.patch(`/novels/${id}`, data).then((r) => r.data),
  deleteNovel: (id) => http.delete(`/novels/${id}`),

  importNovel: (file, fields) => upload('/imports/novel', file, fields),
  getImport: (id) => http.get(`/imports/${id}`).then((r) => r.data),
  deleteSourceDocument: (id) => http.delete(`/source-documents/${id}`),
  listStyleReferences: () => http.get('/style-references').then((r) => r.data),
  createStyleReference: (file, fields) => upload('/style-references', file, fields),

  createComic: (novelId, data) => http.post(`/novels/${novelId}/comics`, data).then((r) => r.data),
  getComic: (id) => http.get(`/comics/${id}`).then((r) => r.data),
  retryComicPanel: (id) => http.post(`/comic-panels/${id}/retry`).then((r) => r.data),

  listCharacters: (novelId) => http.get(`/novels/${novelId}/characters`).then((r) => r.data),
  createCharacter: (novelId, data) =>
    http.post(`/novels/${novelId}/characters`, data).then((r) => r.data),
  updateCharacter: (id, data) => http.patch(`/characters/${id}`, data).then((r) => r.data),
  deleteCharacter: (id) => http.delete(`/characters/${id}`),

  listRelations: (novelId) => http.get(`/novels/${novelId}/relations`).then((r) => r.data),
  createRelation: (novelId, data) =>
    http.post(`/novels/${novelId}/relations`, data).then((r) => r.data),
  updateRelation: (id, data) => http.patch(`/relations/${id}`, data).then((r) => r.data),
  deleteRelation: (id) => http.delete(`/relations/${id}`),

  chapterTree: (novelId) => http.get(`/novels/${novelId}/chapters/tree`).then((r) => r.data),
  getChapter: (id) => http.get(`/chapters/${id}`).then((r) => r.data),
  updateChapter: (id, data) => http.patch(`/chapters/${id}`, data).then((r) => r.data),
  setPrimaryChapter: (id) => http.post(`/chapters/${id}/set-primary`).then((r) => r.data),
  deleteChapter: (id) => http.delete(`/chapters/${id}`),
  generateChapter: (novelId, data) =>
    http.post(`/novels/${novelId}/chapters/generate`, data).then((r) => r.data),
  regenerateChapter: (chapterId, data) =>
    http.post(`/chapters/${chapterId}/regenerate`, data).then((r) => r.data),
  suggestOptions: (novelId, data) =>
    http.post(`/novels/${novelId}/chapters/suggest-options`, data).then((r) => r.data),
}

export function errMsg(err, fallback = '请求失败') {
  const detail = err?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join('; ')
  }
  if (err?.message) return err.message
  return fallback
}

export default http
