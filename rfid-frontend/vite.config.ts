import path from "path"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { inspectAttr } from 'kimi-plugin-inspect-react'

// https://vite.dev/config/
export default defineConfig({
  base: './',
  plugins: [inspectAttr(), react()],
  server: {
    port: 3001,
    // Bind to every interface, not just localhost.
    //
    // Vite defaults to 127.0.0.1, which is reachable only from this machine — so the dev
    // server is invisible to a phone or a booth PC on the same network even though the port
    // is open. `true` is equivalent to passing `--host` and makes it stick for everyone who
    // clones the repo.
    host: true,
    // Fail loudly if 3001 is taken instead of silently moving to 3002 and leaving every
    // bookmarked URL and CORS origin pointing at the wrong port.
    strictPort: true,

    // Proxy the API through this dev server so the BROWSER only ever sees same-origin
    // requests. That is not a convenience — it is what makes login work at all.
    //
    // Calling https://api.maliroperations.com directly from http://<lan-ip>:3001 fails twice
    // over, and neither failure looks like what it is:
    //
    //   1. The API sets its session cookies `SameSite=Lax`. A Lax cookie is stored on a
    //      cross-site response but is NEVER sent on a cross-site fetch, so login returns 200
    //      and every subsequent call is anonymous — the UI just spins.
    //   2. Pointing VITE_API_URL at http:// instead of https:// makes Apache answer the
    //      CORS preflight with a 301 to HTTPS, and browsers do not carry CORS through a
    //      cross-origin redirect. The request never reaches Django.
    //
    // Through this proxy the browser talks to its own origin, so there is no preflight, no
    // CORS, and the cookie comes back as a FIRST-party cookie bound to the dev host — which
    // Lax permits. Vite talks HTTPS to the real API server-side, where none of this applies.
    proxy: {
      '/api': {
        target: 'https://api.maliroperations.com',
        // Rewrites the Host header to the target, which Django checks against
        // ALLOWED_HOSTS before any view runs. Without it every request 400s.
        changeOrigin: true,
        secure: true,
        // Strip any Domain attribute so the cookie binds to whatever host the developer
        // opened — localhost, the LAN IP, a tunnel — instead of the API's domain, which the
        // browser would then refuse to store.
        cookieDomainRewrite: '',
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
});
