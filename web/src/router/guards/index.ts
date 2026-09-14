import type { Router } from "vue-router";
import { useAuthGuard } from "./auth";
import { useProgressGuard } from "./progress";
import { useRedirectGuard } from "./redirect";

const guards = [useRedirectGuard, useAuthGuard, useProgressGuard];

export function setupRouterGuard(router: Router) {
  for (const guard of guards) {
    guard(router);
  }
}
