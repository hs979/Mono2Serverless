<template>
  <v-container class="fill-height" fluid>
    <v-row align="center" justify="center">
      <v-col cols="12" sm="8" md="4">
        <v-card class="elevation-12">
          <v-toolbar color="primary" dark flat>
            <v-toolbar-title>{{ isLogin ? '登录' : '注册' }}</v-toolbar-title>
            <v-spacer></v-spacer>
          </v-toolbar>
          <v-card-text>
            <v-form ref="form" v-model="valid">
              <v-text-field
                v-model="username"
                label="用户名"
                prepend-icon="mdi-account"
                type="text"
                :rules="usernameRules"
                required
              ></v-text-field>

              <v-text-field
                v-if="!isLogin"
                v-model="email"
                label="邮箱（可选）"
                prepend-icon="mdi-email"
                type="email"
              ></v-text-field>

              <v-text-field
                v-model="password"
                label="密码"
                prepend-icon="mdi-lock"
                :type="showPassword ? 'text' : 'password'"
                :append-icon="showPassword ? 'mdi-eye' : 'mdi-eye-off'"
                @click:append="showPassword = !showPassword"
                :rules="passwordRules"
                required
              ></v-text-field>

              <v-text-field
                v-if="!isLogin"
                v-model="confirmPassword"
                label="确认密码"
                prepend-icon="mdi-lock-check"
                :type="showPassword ? 'text' : 'password'"
                :rules="confirmPasswordRules"
                required
              ></v-text-field>
            </v-form>

            <v-alert v-if="errorMessage" type="error" dense class="mt-4">
              {{ errorMessage }}
            </v-alert>

            <v-alert v-if="successMessage" type="success" dense class="mt-4">
              {{ successMessage }}
            </v-alert>
          </v-card-text>

          <v-card-actions>
            <v-btn
              text
              color="primary"
              @click="toggleMode"
            >
              {{ isLogin ? '还没有账户？点击注册' : '已有账户？点击登录' }}
            </v-btn>
            <v-spacer></v-spacer>
            <v-btn
              color="primary"
              :disabled="!valid || loading"
              :loading="loading"
              @click="handleSubmit"
            >
              {{ isLogin ? '登录' : '注册' }}
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script>
import { login, register } from '@/backend/api.js'

export default {
  name: 'Auth',
  data() {
    return {
      isLogin: true,
      valid: false,
      loading: false,
      username: '',
      email: '',
      password: '',
      confirmPassword: '',
      showPassword: false,
      errorMessage: '',
      successMessage: '',
      usernameRules: [
        v => !!v || '用户名不能为空',
        v => (v && v.length >= 3) || '用户名至少3个字符'
      ],
      passwordRules: [
        v => !!v || '密码不能为空',
        v => (v && v.length >= 6) || '密码至少6个字符'
      ],
      confirmPasswordRules: [
        v => !!v || '请确认密码',
        v => v === this.password || '两次输入的密码不一致'
      ]
    }
  },
  methods: {
    toggleMode() {
      this.isLogin = !this.isLogin
      this.errorMessage = ''
      this.successMessage = ''
      this.clearForm()
    },
    clearForm() {
      this.username = ''
      this.email = ''
      this.password = ''
      this.confirmPassword = ''
      if (this.$refs.form) {
        this.$refs.form.resetValidation()
      }
    },
    async handleSubmit() {
      if (!this.$refs.form.validate()) {
        return
      }

      this.loading = true
      this.errorMessage = ''
      this.successMessage = ''

      try {
        if (this.isLogin) {
          // 登录
          await login(this.username, this.password)
          this.successMessage = '登录成功！'
          
          // 迁移购物车
          await this.$store.dispatch('migrateCart')
          
          // 延迟跳转到首页
          setTimeout(() => {
            this.$router.push('/')
          }, 500)
        } else {
          // 注册
          await register(this.username, this.password, this.email)
          this.successMessage = '注册成功！请登录'
          
          // 切换到登录模式
          setTimeout(() => {
            this.isLogin = true
            this.clearForm()
          }, 1500)
        }
      } catch (error) {
        if (error.response && error.response.data && error.response.data.message) {
          this.errorMessage = error.response.data.message
        } else {
          this.errorMessage = this.isLogin ? '登录失败，请检查用户名和密码' : '注册失败，请稍后重试'
        }
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style scoped>
.fill-height {
  min-height: 100vh;
}
</style>
