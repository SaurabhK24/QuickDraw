package handlers

import (
	"encoding/json"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/quickdraw/controlplane/internal/middleware"
)

func jsonResp(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func tenant(r *http.Request) string {
	if v, ok := r.Context().Value(middleware.TenantIDKey).(string); ok {
		return v
	}
	return "default"
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------

func Health(w http.ResponseWriter, r *http.Request) {
	jsonResp(w, http.StatusOK, map[string]string{
		"status":    "ok",
		"service":   "quickdraw-control-plane",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// ---------------------------------------------------------------------------
// Runs
// ---------------------------------------------------------------------------

func CreateRun(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	json.NewDecoder(r.Body).Decode(&body)

	jsonResp(w, http.StatusAccepted, map[string]any{
		"run_id":    "stub-run-id",
		"tenant":    tenant(r),
		"status":    "pending",
		"message":   "Run creation will be wired to Temporal in Phase 3",
	})
}

func GetRun(w http.ResponseWriter, r *http.Request) {
	runID := chi.URLParam(r, "runID")
	jsonResp(w, http.StatusOK, map[string]any{
		"run_id": runID,
		"tenant": tenant(r),
		"status": "stub",
	})
}

func CancelRun(w http.ResponseWriter, r *http.Request) {
	runID := chi.URLParam(r, "runID")
	jsonResp(w, http.StatusOK, map[string]any{
		"run_id":  runID,
		"status":  "cancelled",
		"message": "Cancellation will signal Temporal in Phase 3",
	})
}

// ---------------------------------------------------------------------------
// Approvals
// ---------------------------------------------------------------------------

func ApprovalDecision(w http.ResponseWriter, r *http.Request) {
	approvalID := chi.URLParam(r, "approvalID")
	jsonResp(w, http.StatusOK, map[string]any{
		"approval_id": approvalID,
		"status":      "acknowledged",
		"message":     "Approval decisions will resume Temporal workflows in Phase 3",
	})
}

// ---------------------------------------------------------------------------
// Agents
// ---------------------------------------------------------------------------

func ListAgents(w http.ResponseWriter, r *http.Request) {
	jsonResp(w, http.StatusOK, map[string]any{
		"agents": []map[string]string{
			{"id": "main", "name": "Jarvis"},
		},
		"tenant": tenant(r),
	})
}

func CreateAgent(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	json.NewDecoder(r.Body).Decode(&body)
	jsonResp(w, http.StatusCreated, map[string]any{
		"status":  "created",
		"tenant":  tenant(r),
		"message": "Agent persistence will use Postgres models from Phase 1",
	})
}

// ---------------------------------------------------------------------------
// Workflows
// ---------------------------------------------------------------------------

func CreateWorkflow(w http.ResponseWriter, r *http.Request) {
	var body map[string]any
	json.NewDecoder(r.Body).Decode(&body)
	jsonResp(w, http.StatusCreated, map[string]any{
		"status":  "created",
		"tenant":  tenant(r),
		"message": "Workflow persistence will use Postgres models from Phase 1",
	})
}

// ---------------------------------------------------------------------------
// Events (SSE stub)
// ---------------------------------------------------------------------------

func EventStream(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.WriteHeader(http.StatusOK)

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	data, _ := json.Marshal(map[string]string{
		"type":    "connected",
		"tenant":  tenant(r),
		"message": "Event streaming will emit run and approval events",
	})
	w.Write([]byte("data: "))
	w.Write(data)
	w.Write([]byte("\n\n"))
	flusher.Flush()
}
