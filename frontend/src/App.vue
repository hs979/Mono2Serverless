<template>
  <v-app>
    <v-app-bar elevate-on-scroll app class="primary">
      <v-toolbar-title>
        <router-link tag="div" to="/">
          <a class="accent--text header font-weight-black">
            DEMO
            <span class="font-weight-thin subheading secondary--text">Store</span>
          </a>
        </router-link>
      </v-toolbar-title>
      <v-toolbar-items>
        <v-btn to="/auth" v-if="!currentUser" text class="ml-2">登录 / 注册</v-btn>
        <cart-button @drawerChange="toggleDrawer" />
        <div class="sign-out" v-if="currentUser">
          <v-btn text @click="logout" class="pl-2">
            <v-icon left>mdi-logout</v-icon>
            登出 ({{ currentUser.username }})
          </v-btn>
        </div>
      </v-toolbar-items>
    </v-app-bar>
    <v-main>
      <v-container fluid>
        <loading-overlay />
        <v-fade-transition mode="out-in">
          <router-view></router-view>
        </v-fade-transition>
      </v-container>
      <v-navigation-drawer
        style="position:fixed; overflow-y:scroll;"
        right
        v-model="drawer"
        temporary
        align-space-around
        column
        d-flex
      >
        <cart-drawer />
      </v-navigation-drawer>
    </v-main>
  </v-app>
</template>

<script>
import { mapGetters, mapState } from "vuex";

export default {
  name: "app",
  data() {
    return {
      drawer: null
    };
  },
  mounted() {
    // 初始化用户状态
    this.$store.dispatch("initAuth");
    // 获取购物车
    this.$store.dispatch("fetchCart");
  },
  computed: {
    ...mapGetters(["cartSize", "currentUser"]),
    ...mapState(["cartLoading"])
  },
  methods: {
    logout() {
      this.$store.dispatch("logout");
      this.$router.push("/");
    },
    toggleDrawer() {
      this.drawer = !this.drawer;
    }
  }
};
</script>

<style>
.header {
  font-weight: bold !important;
  font-size: 30px !important;
  text-decoration: none;
  cursor: pointer;
}

:root {
  /* Colors */
  --amazonOrange: #e88b01 !important;
}
</style>
