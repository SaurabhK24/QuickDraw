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

	switch status {
	case "Completed", "WORKFLOW_EXECUTION_STATUS_COMPLETED":
		run := Client.GetWorkflow(ctx, workflowID, "")
		var output AgentRunOutput
		if err := run.Get(ctx, &output); err != nil {
			return nil, status, fmt.Errorf("get result: %w", err)
		}
		return &output, "completed", nil

	case "Running", "WORKFLOW_EXECUTION_STATUS_RUNNING":
		result, err := QueryRunResult(ctx, workflowID)
		if err != nil {
			return nil, "running", nil
		}
		return result, "running", nil

	case "Failed", "WORKFLOW_EXECUTION_STATUS_FAILED":
		return nil, "failed", nil

	case "Canceled", "Cancelled", "WORKFLOW_EXECUTION_STATUS_CANCELED":
		return nil, "cancelled", nil

	case "Terminated", "WORKFLOW_EXECUTION_STATUS_TERMINATED":
		return nil, "terminated", nil

	case "TimedOut", "WORKFLOW_EXECUTION_STATUS_TIMED_OUT":
		return nil, "timed_out", nil

	default:
		return nil, status, nil
	}
}

func QueryRunResult(ctx context.Context, workflowID string) (*AgentRunOutput, error) {
	resp, err := Client.QueryWorkflow(ctx, workflowID, "", "get_result")
	if err != nil {
		return nil, fmt.Errorf("query workflow: %w", err)
	}
	var output AgentRunOutput
	if err := resp.Get(&output); err != nil {
		return nil, fmt.Errorf("decode query result: %w", err)
	}
	if output.ResponseText == "" {
		return nil, nil
	}
	return &output, nil
}

func CancelRun(ctx context.Context, workflowID string) error {
	return Client.CancelWorkflow(ctx, workflowID, "")
}

func SignalApproval(ctx context.Context, workflowID string, approved bool) error {
	return Client.SignalWorkflow(ctx, workflowID, "", "approve", approved)
}

type StepApprovalData struct {
	StepIndex int  `json:"step_index"`
	Approved  bool `json:"approved"`
}

func SignalStepApproval(ctx context.Context, workflowID string, stepIndex int, approved bool) error {
	return Client.SignalWorkflow(ctx, workflowID, "", "approve_step", StepApprovalData{
		StepIndex: stepIndex,
		Approved:  approved,
	})
}

// RouterInput matches the Python RouterInput dataclass.
type RouterInput struct {
	TenantID           string                   `json:"tenant_id"`
	SessionKey         string                   `json:"session_key"`
	UserText           string                   `json:"user_text"`
	Model              string                   `json:"model"`
	MaxTokens          int                      `json:"max_tokens"`
	PackContext        string                   `json:"pack_context"`
	AvailableWorkflows []map[string]interface{} `json:"available_workflows"`
}

// RouterOutput matches the Python RouterOutput dataclass.
type RouterOutput struct {
	ResponseText string `json:"response_text"`
	RoutedTo     string `json:"routed_to"`
	RouteType    string `json:"route_type"`
	StepCount    int    `json:"step_count"`
}

func StartRouterRun(ctx context.Context, input RouterInput) (string, string, error) {
	opts := client.StartWorkflowOptions{
		TaskQueue: TaskQueue,
	}
	run, err := Client.ExecuteWorkflow(ctx, opts, "RouterWorkflow", input)
	if err != nil {
		return "", "", fmt.Errorf("start router workflow: %w", err)
	}
	return run.GetID(), run.GetRunID(), nil
}

// PackContext is set at startup by the main function and passed to router runs.
var PackContext string
var AvailableWorkflows []map[string]interface{}
