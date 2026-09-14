import type { Router } from "vue-router";
import NProgress from "nprogress";

NProgress.configure({
  showSpinner: false,
});

export function useProgressGuard(router: Router) {
  router.beforeEach((to, from) => {
    if (to.path !== from.path) {
      NProgress.start();
    }
    return true;
  });

  router.afterEach(() => {
    NProgress.done();
  });
}
