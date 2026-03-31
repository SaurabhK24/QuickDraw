package middleware

import (
	"context"
	"net/http"
)

type contextKey string

const (
	TenantIDKey contextKey = "tenant_id"
	UserIDKey   contextKey = "user_id"
)

// AuthMiddleware validates bearer tokens. Currently a pass-through stub
// that sets a dev user identity. Replace with OIDC validation.
func AuthMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// TODO: validate Authorization header, extract claims
		ctx := context.WithValue(r.Context(), UserIDKey, "dev-user")
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

// TenantResolver extracts tenant from X-Tenant-ID header or defaults.
func TenantResolver(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		tenantID := r.Header.Get("X-Tenant-ID")
		if tenantID == "" {
			tenantID = "default"
		}
		ctx := context.WithValue(r.Context(), TenantIDKey, tenantID)
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}
