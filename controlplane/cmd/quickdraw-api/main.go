package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"

	"github.com/go-chi/chi/v5"
	chimw "github.com/go-chi/chi/v5/middleware"
	"github.com/go-chi/cors"
	"github.com/quickdraw/controlplane/internal/handlers"
	"github.com/quickdraw/controlplane/internal/middleware"
	"github.com/quickdraw/controlplane/internal/temporal"
)

func main() {
	port := envOr("PORT", "8080")
	pythonBackend := envOr("PYTHON_BACKEND", "http://127.0.0.1:5000")

	if agentsJSON := os.Getenv("AGENTS_CONFIG"); agentsJSON != "" {
		var agents []map[string]string
		if err := json.Unmarshal([]byte(agentsJSON), &agents); err != nil {
			log.Printf("AGENTS_CONFIG parse error (using default): %v", err)
		} else {
			handlers.RegisteredAgents = agents
			log.Printf("Loaded %d agents from AGENTS_CONFIG", len(agents))
		}
	}

	if err := temporal.Connect(); err != nil {
		log.Fatalf("Temporal: %v", err)
	}
	defer temporal.Close()

	r := chi.NewRouter()

	r.Use(chimw.Logger)
	r.Use(chimw.Recoverer)
	r.Use(chimw.RequestID)
	r.Use(cors.Handler(cors.Options{
		AllowedOrigins: []string{"*"},
		AllowedMethods: []string{"GET", "POST", "PUT", "DELETE", "OPTIONS"},
		AllowedHeaders: []string{"*"},
	}))
	r.Use(middleware.TenantResolver)

	r.Get("/health", handlers.Health)

	r.Route("/v1", func(r chi.Router) {
		r.Use(middleware.AuthMiddleware)

		r.Post("/runs", handlers.CreateRun)
		r.Get("/runs/{runID}", handlers.GetRun)
		r.Post("/runs/{runID}/cancel", handlers.CancelRun)

		r.Post("/approvals/{approvalID}/decision", handlers.ApprovalDecision)

		r.Get("/agents", handlers.ListAgents)
		r.Post("/agents", handlers.CreateAgent)

		r.Post("/workflows", handlers.CreateWorkflow)

		r.Post("/chat/send", handlers.ChatSend)

		r.Get("/events/stream", handlers.EventStream)
	})

	handlers.PythonBackend = pythonBackend

	backendURL, err := url.Parse(pythonBackend)
	if err != nil {
		log.Fatalf("invalid PYTHON_BACKEND: %v", err)
	}
	proxy := httputil.NewSingleHostReverseProxy(backendURL)
	r.Post("/chat", func(w http.ResponseWriter, r *http.Request) {
		proxy.ServeHTTP(w, r)
	})
	r.Get("/chat/health", func(w http.ResponseWriter, r *http.Request) {
		proxy.ServeHTTP(w, r)
	})
	r.Get("/sessions", func(w http.ResponseWriter, r *http.Request) {
		proxy.ServeHTTP(w, r)
	})
	r.Get("/sessions/{key}", func(w http.ResponseWriter, r *http.Request) {
		proxy.ServeHTTP(w, r)
	})
	r.Get("/progress", func(w http.ResponseWriter, r *http.Request) {
		proxy.ServeHTTP(w, r)
	})

	addr := fmt.Sprintf(":%s", port)
	log.Printf("QuickDraw control plane listening on %s", addr)
	log.Printf("Proxying /chat -> %s", pythonBackend)
	log.Fatal(http.ListenAndServe(addr, r))
}

func envOr(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
