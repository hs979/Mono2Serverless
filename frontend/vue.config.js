module.exports = {
  "transpileDependencies": [
    "vuetify",
     'aws-amplify',
    '@aws-amplify'
  ],
  lintOnSave: false,
  // 构建输出目录
  outputDir: 'dist',
  // 开发服务器配置
  devServer: {
    port: 8080,
    proxy: {
      // 代理所有/auth、/cart、/product请求到后端Flask服务
      '^/(auth|cart|product)': {
        target: 'http://localhost:5000',
        changeOrigin: true,
        ws: false
      }
    }
  }
}
