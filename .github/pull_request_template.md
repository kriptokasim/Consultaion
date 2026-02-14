## Pull Request Checklist

- [ ] No hardcoded `onrender.com`, `vercel.app`, or `localhost:` in app code
- [ ] Uses `NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_APP_URL` via `@/lib/config/runtime`
- [ ] `npm run lint:urls` passes cleanly
- [ ] New API calls use `API_ORIGIN` / `apiUrl()` from the runtime config module
