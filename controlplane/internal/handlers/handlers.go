package handlers

import (
	"encoding/json"
	"fmt"
	"net/http"
	"time"

	"github.com/go-chi/chi/v5"
	"github.com/quickdraw/controlplane/internal/middleware"
	"github.com/quickdraw/controlplane/internal/temporal"
)

// PythonBackend is the URL of the quickdraw-python gateway (set by main.go).
var PythonBackend string

func jsonResp(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(v)
}

func jsonErr(w http.ResponseWriter, status int, msg string) {
	jsonResp(w, status, map[string]string{"error": msg})
}

func tenant(r *http.Request) string {
	if v, ok := r.Context().Value(middleware.TenantIDKey).(string); ok {
		return v
	}
	return "default"
}

// Health returns service status.
func Health(w http.ResponseWriter, r *http.Request) {
	jsonResp(w, http.StatusOK, map[string]string{
		"status":    "ok",
		"service":   "quickdraw-control-plane",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

// ---------------------------------------------------------------------------
// Runs — wired to Temporal
// ---------------------------------------------------------------------------

type createRunRequest struct {
	AgentID          string `json:"agent_id"`
	UserText         string `json:"user_text"`
	SessionKey       string `json:"session_key"`
	Model            string `json:"model"`
	MaxTokens        int    `json:"max_tokens"`
	RequiresApproval bool   `json:"requires_approval"`
	Mode             string `json:"mode"`
}

func CreateRun(w http.ResponseWriter, r *http.Request) {
	var body createRunRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	if body.UserText == "" {
		jsonErr(w, http.StatusBadRequest, "user_text is required")
		return
	}
	if body.SessionKey == "" {
		body.SessionKey = "api:" + tenant(r)
	}
	if body.Model == "" {
		body.Model = "claude-sonnet-4-5-20250929"
	}
	if body.MaxTokens == 0 {
		body.MaxTokens = 4096
	}

	if body.Mode == "routed" || (body.Mode == "" && body.AgentID == "") {
		input := temporal.RouterInput{
			TenantID:           tenant(r),
			SessionKey:         body.SessionKey,
			UserText:           body.UserText,
			Model:              body.Model,
			MaxTokens:          body.MaxTokens,
			PackContext:        temporal.PackContext,
			AvailableWorkflows: temporal.AvailableWorkflows,
		}

		workflowID, runID, err := temporal.StartRouterRun(r.Context(), input)
		if err != nil {
			jsonErr(w, http.StatusInternalServerError, "failed to start routed run: "+err.Error())
			return
		}

		jsonResp(w, http.StatusAccepted, map[string]any{
			"workflow_id": workflowID,
			"run_id":      runID,
			"session_key": body.SessionKey,
			"tenant":      tenant(r),
			"status":      "running",
			"mode":        "routed",
		})
		return
	}

	if body.AgentID == "" {
		body.AgentID = "main"
	}

	input := temporal.DurableRunInput{
		TenantID:         tenant(r),
		SessionKey:       body.SessionKey,
		AgentID:          body.AgentID,
		UserText:         body.UserText,
		Model:            body.Model,
		MaxTokens:        body.MaxTokens,
		RequiresApproval: body.RequiresApproval,
	}

	workflowID, runID, err := temporal.StartRun(r.Context(), input)
	if err != nil {
		jsonErr(w, http.StatusInternalServerError, "failed to start run: "+err.Error())
		return
	}

	jsonResp(w, http.StatusAccepted, map[string]any{
		"workflow_id": workflowID,
		"run_id":      runID,
		"session_key": body.SessionKey,
		"tenant":      tenant(r),
		"status":      "running",
		"mode":        "direct",
	})
}

func GetRun(w http.ResponseWriter, r *http.Request) {
	workflowID := chi.URLParam(r, "runID")

	output, status, err := temporal.GetRunResult(r.Context(), workflowID)
	if err != nil {
		jsonErr(w, http.StatusInternalServerError, "failed to get run: "+err.Error())
		return
	}

	resp := map[string]any{
		"workflow_id": workflowID,
		"tenant":      tenant(r),
		"status":      status,
	}
	if output != nil {
		resp["response_text"] = output.ResponseText
		resp["step_count"] = output.StepCount
		resp["run_id"] = output.RunID
	}

	// If still running and query returned partial result, mark it
	if status == "running" && output != nil {
		resp["partial"] = true
	}

	jsonResp(w, http.StatusOK, resp)
}

func CancelRun(w http.ResponseWriter, r *http.Request) {
	workflowID := chi.URLParam(r, "runID")

	if err := temporal.CancelRun(r.Context(), workflowID); err != nil {
		jsonErr(w, http.StatusInternalServerError, "failed to cancel: "+err.Error())
		return
	}

	jsonResp(w, http.StatusOK, map[string]any{
		"workflow_id": workflowID,
		"status":      "cancelled",
	})
}

// ---------------------------------------------------------------------------
// Approvals — signal a running workflow
// ---------------------------------------------------------------------------

type approvalRequest struct {
	Approved bool `json:"approved"`
}

func ApprovalDecision(w http.ResponseWriter, r *http.Request) {
	workflowID := chi.URLParam(r, "approvalID")

	var body approvalRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	if err := temporal.SignalApproval(r.Context(), workflowID, body.Approved); err != nil {
		jsonErr(w, http.StatusInternalServerError, "failed to signal approval: "+err.Error())
		return
	}

	jsonResp(w, http.StatusOK, map[string]any{
		"workflow_id": workflowID,
		"approved":    body.Approved,
		"status":      "signaled",
	})
}

// ---------------------------------------------------------------------------
// Agents — read from config (no DB yet)
// ---------------------------------------------------------------------------

var RegisteredAgents = []map[string]string{
	{"id": "main", "name": "Jarvis"},
	{"id": "core.supervisor", "name": "Supervisor"},
}

func ListAgents(w http.ResponseWriter, r *http.Request) {
	jsonResp(w, http.StatusOK, map[string]any{
		"agents": RegisteredAgents,
		"tenant": tenant(r),
	})
}

func CreateAgent(w http.ResponseWriter, r *http.Request) {
	jsonErr(w, http.StatusNotImplemented, "agent creation requires database (future phase)")
}

// ---------------------------------------------------------------------------
// Workflows
// ---------------------------------------------------------------------------

func CreateWorkflow(w http.ResponseWriter, r *http.Request) {
	jsonErr(w, http.StatusNotImplemented, "workflow creation requires database (future phase)")
}

// ---------------------------------------------------------------------------
// Chat — convenience wrapper for multi-turn conversations
// ---------------------------------------------------------------------------

type chatSendRequest struct {
	UserText   string `json:"user_text"`
	SessionKey string `json:"session_key"`
	Model      string `json:"model"`
}

func ChatSend(w http.ResponseWriter, r *http.Request) {
	var body chatSendRequest
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErr(w, http.StatusBadRequest, "invalid JSON body")
		return
	}

	if body.UserText == "" {
		jsonErr(w, http.StatusBadRequest, "user_text is required")
		return
	}
	if body.SessionKey == "" {
		body.SessionKey = fmt.Sprintf("chat:%s:%d", tenant(r), time.Now().UnixMilli())
	}
	if body.Model == "" {
		body.Model = "claude-sonnet-4-5-20250929"
	}

	input := temporal.RouterInput{
		TenantID:           tenant(r),
		SessionKey:         body.SessionKey,
		UserText:           body.UserText,
		Model:              body.Model,
		MaxTokens:          8192,
		PackContext:        temporal.PackContext,
		AvailableWorkflows: temporal.AvailableWorkflows,
	}

	workflowID, runID, err := temporal.StartRouterRun(r.Context(), input)
	if err != nil {
		jsonErr(w, http.StatusInternalServerError, "failed to start chat run: "+err.Error())
		return
	}

	jsonResp(w, http.StatusAccepted, map[string]any{
		"workflow_id": workflowID,
		"run_id":      runID,
		"session_key": body.SessionKey,
		"tenant":      tenant(r),
		"status":      "running",
		"mode":        "routed",
	})
}

// ---------------------------------------------------------------------------
// Events (SSE)
// ---------------------------------------------------------------------------

func EventStream(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("X-Accel-Buffering", "no")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming not supported", http.StatusInternalServerError)
		return
	}

	workflowID := r.URL.Query().Get("workflow_id")
	sessionKey := r.URL.Query().Get("session_key")

	sendSSE(w, flusher, "connected", map[string]string{"tenant": tenant(r)})

	if workflowID == "" {
		<-r.Context().Done()
		return
	}

	ticker := time.NewTicker(2 * time.Second)
	defer ticker.Stop()
	lastProgressIdx := 0

	for {
		select {
		case <-r.Context().Done():
			return
		case <-ticker.C:
			// Poll delegation progress from the Python gateway
			if sessionKey != "" && PythonBackend != "" {
				newEvents, newIdx := fetchDelegationProgress(sessionKey, lastProgressIdx)
				for _, evt := range newEvents {
					sendSSE(w, flusher, "delegation", evt)
				}
				lastProgressIdx = newIdx
			}

			// Poll Temporal for workflow status
			output, status, err := temporal.GetRunResult(r.Context(), workflowID)
			if err != nil {
				sendSSE(w, flusher, "error", map[string]string{"error": err.Error()})
				return
			}

			event := map[string]any{
				"workflow_id": workflowID,
				"status":      status,
			}

			if output != nil {
				event["response_text"] = output.ResponseText
				event["step_count"] = output.StepCount
			}

			switch status {
			case "completed":
				sendSSE(w, flusher, "result", event)
				return
			case "failed", "cancelled", "terminated", "timed_out":
				sendSSE(w, flusher, "status", event)
				return
			default:
				sendSSE(w, flusher, "progress", event)
			}
		}
	}
}

func fetchDelegationProgress(sessionKey string, since int) ([]map[string]any, int) {
	if PythonBackend == "" {
		return nil, since
	}
	url := fmt.Sprintf("%s/progress?key=%s&since=%d", PythonBackend, sessionKey, since)
	resp, err := http.Get(url)
	if err != nil || resp.StatusCode != 200 {
		return nil, since
	}
	defer resp.Body.Close()

	var data struct {
		Events []map[string]any `json:"events"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, since
	}
	return data.Events, since + len(data.Events)
}

func sendSSE(w http.ResponseWriter, flusher http.Flusher, eventType string, data any) {
	jsonData, _ := json.Marshal(data)
	fmt.Fprintf(w, "event: %s\ndata: %s\n\n", eventType, jsonData)
	flusher.Flush()
}
