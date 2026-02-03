import VueRouter from 'vue-router'
import Vue from 'vue';
import store from '@/store/store.js'
import Home from '@/views/Home.vue'
import Payment from '@/views/Payment.vue'
import Auth from '@/views/Auth.vue'
import { getCurrentUser } from '@/backend/api.js'

// 获取当前用户（从localStorage）
function getUser() {
  const user = getCurrentUser()
  if (user) {
    store.commit('setUser', user)
    return Promise.resolve(user)
  }
  return Promise.resolve(null)
}
const routes = [{
    path: '/',
    component: Home
  },
  {
    path: '/auth',
    name: 'Authenticator',
    component: Auth
  }, {
    path: '/checkout',
    component: Payment,
    meta: {
      requiresAuth: true
    }
  }
]

const router = new VueRouter({
  mode: 'history',
  routes
})

router.beforeResolve(async (to, from, next) => {
  if (to.matched.some(record => record.meta.requiresAuth)) {
    let user = await getUser();
    if (!user) {
      return next({
        path: '/auth',
        query: {
          redirect: to.fullPath,
        }
      });
    }
    return next()
  }
  return next()
})

export default router