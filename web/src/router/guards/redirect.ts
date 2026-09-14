import type { Router } from "vue-router";

export function useRedirectGuard(router: Router) {
  router.beforeEach(async (to) => {
    const redirect = to.meta.redirect?.replace(/:(\w+)/g, (_, p1: string) => {
      const value = to.params[p1 as keyof typeof to.params];
      if (value === undefined) {
        return "";
      }
      return value;
    });

    if (redirect === to.path) {
      return true;
    }

    if (redirect) {
      return redirect;
    }

    return true;
  });
}
