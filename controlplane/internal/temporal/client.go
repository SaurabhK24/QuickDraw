package temporal

import (
	"context"
	"fmt"
	"log"
	"os"
	"time"

	"go.temporal.io/sdk/client"
)

const TaskQueue = "quickdraw-runs"

var Client client.Client

func Connect() error {
	addr := os.Getenv("TEMPORAL_ADDRESS")
	if addr == "" {
		addr = "localhost:7233"
	}

	var err error
	for attempt := 1; attempt <= 20; attempt++ {
		Client, err = client.Dial(client.Options{HostPort: addr})
		if err == nil {
			log.Printf("Temporal connected at %s", addr)
			return nil
		}
		log.Printf("Temporal connect attempt %d failed: %v", attempt, err)
		time.Sleep(3 * time.Second)
	}
	return fmt.Errorf("failed to connect to Temporal at %s after retries: %w", addr, err)
}

func Close() {
	if Client != nil {
		Client.Close()
	}
}

// DurableRunInput must match the Python DurableRunInput dataclass field names exactly.
type DurableRunInput struct {
	TenantID         string `json:"tenant_id"`
	SessionKey       string `json:"session_key"`
	AgentID          string `json:"agent_id"`
	UserText         string `json:"user_text"`
	Model            string `json:"model"`
	MaxTokens        int    `json:"max_tokens"`
	RequiresApproval bool   `json:"requires_approval"`
}

// AgentRunOutput must match the Python AgentRunOutput dataclass field names exactly.
type AgentRunOutput struct {
	ResponseText string `json:"response_text"`
	RunID        string `json:"run_id"`
	StepCount    int    `json:"step_count"`
}

func StartRun(ctx context.Context, input DurableRunInput) (string, string, error) {
	opts := client.StartWorkflowOptions{
		TaskQueue: TaskQueue,
	}
	run, err := Client.ExecuteWorkflow(ctx, opts, "DurableRunWorkflow", input)
	if err != nil {
		return "", "", fmt.Errorf("start workflow: %w", err)
	}
	return run.GetID(), run.GetRunID(), nil
}

func GetRunResult(ctx context.Context, workflowID string) (*AgentRunOutput, string, error) {
	desc, err := Client.DescribeWorkflowExecution(ctx, workflowID, "")
	if err != nil {
		return nil, "", fmt.Errorf("describe workflow: %w", err)
	}
	status := desc.WorkflowExecutionInfo.Status.String()

	// Only try to get result if the workflow completed
	if status == "Completed" {
		run := Client.GetWorkflow(ctx, workflowID, "")
		var output AgentRunOutput
		if err := run.Get(ctx, &output); err != nil {
			return nil, status, fmt.Errorf("get result: %w", err)
		}
		return &output, status, nil
	}

	return nil, status, nil
}

func CancelRun(ctx context.Context, workflowID string) error {
	return Client.CancelWorkflow(ctx, workflowID, "")
}

func SignalApproval(ctx context.Context, workflowID string, approved bool) error {
	return Client.SignalWorkflow(ctx, workflowID, "", "approve", approved)
}
