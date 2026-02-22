import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, {
  addEdge,
  Background,
  Connection,
  Controls,
  MiniMap,
  Node,
  OnConnect,
  useEdgesState,
  useNodesState,
} from "reactflow";

type NodeCatalogItem = {
  type: string;
  description: string;
};

type ToolCatalogItem = {
  name: string;
  description: string;
};

type AgentStep = {
  name: string;
  system_prompt: string;
  tools: string[];
  model?: string;
};

type WorkflowNodeData = {
  label: string;
  type: string;
  params: Record<string, unknown>;
};

type WorkflowPayload = {
  id: string;
  name: string;
  nodes: Array<{ id: string; type: string; params: Record<string, unknown> }>;
  edges: Record<string, string[]>;
  active: boolean;
};

type AgentConfig = {
  model: string;
  system_prompt?: string;
  input_field?: string;
  num_ctx: number;
  num_predict: number;
  temperature: number;
  tools?: string[];
  max_tool_calls?: number;
};

type AppConfigResponse = {
  agent_defaults: AgentConfig;
  multi_agent_defaults?: {
    model: string;
    input_field: string;
    num_ctx: number;
    num_predict: number;
    temperature: number;
    max_tool_calls: number;
    agents: Array<Record<string, unknown>>;
  };
  profile_8gb: AgentConfig;
  agent_tools?: {
    allow_http_domains?: string[];
    tavily_max_results?: number;
  };
};

type ExecutionResponse = {
  id: string;
  workflow_id: string;
  status: string;
  started_at: string;
  finished_at: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
};

const API_BASE = "http://127.0.0.1:8000";

const fallbackAgentDefaults: AgentConfig = {
  model: "qwen2.5:1.5b",
  system_prompt: "You are a helpful workflow agent.",
  input_field: "message",
  num_ctx: 1024,
  num_predict: 128,
  temperature: 0.2,
  tools: ["calculator", "utc_time", "tavily_search"],
  max_tool_calls: 6,
};

const fallbackAgentSteps: AgentStep[] = [
  {
    name: "agent_1",
    system_prompt: "You are a factual workflow agent. Use tools before answering factual/current questions.",
    tools: ["calculator", "utc_time", "tavily_search"],
  },
];

const normalizeAgentSteps = (value: unknown): AgentStep[] => {
  if (!Array.isArray(value)) return [];
  const out: AgentStep[] = [];
  for (const item of value) {
    if (!item || typeof item !== "object") continue;
    const row = item as Record<string, unknown>;
    const name = typeof row.name === "string" ? row.name : "";
    const systemPrompt = typeof row.system_prompt === "string" ? row.system_prompt : "";
    const tools = Array.isArray(row.tools)
      ? row.tools.filter((tool): tool is string => typeof tool === "string")
      : [];
    out.push({
      name: name || `agent_${out.length + 1}`,
      system_prompt: systemPrompt,
      tools,
      model: typeof row.model === "string" && row.model ? row.model : undefined,
    });
  }
  return out;
};

const buildDefaultNodeParams = (
  agentDefaults: AgentConfig,
  agentSteps: AgentStep[]
): Record<string, Record<string, unknown>> => ({
  manual_trigger: {},
  set_fields: { fields: { key: "value" } },
  template: { template: "Execution payload => {{json}}" },
  langgraph_agent: {
    model: agentDefaults.model,
    system_prompt: agentDefaults.system_prompt ?? "You are a helpful workflow agent.",
    input_field: agentDefaults.input_field ?? "message",
    num_ctx: agentDefaults.num_ctx,
    num_predict: agentDefaults.num_predict,
    temperature: agentDefaults.temperature,
    tools: agentDefaults.tools ?? ["calculator", "utc_time", "tavily_search"],
    max_tool_calls: agentDefaults.max_tool_calls ?? 6,
    agents: agentSteps.length > 0 ? agentSteps : fallbackAgentSteps,
  },
});

const initialNodes: Node<WorkflowNodeData>[] = [
  {
    id: "n1",
    position: { x: 120, y: 120 },
    data: {
      label: "Start",
      type: "manual_trigger",
      params: {},
    },
  },
];

export function App() {
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [catalog, setCatalog] = useState<NodeCatalogItem[]>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>("n1");
  const [workflowId, setWorkflowId] = useState("visual-agent-flow");
  const [workflowName, setWorkflowName] = useState("Visual Agent Flow");
  const [runInput, setRunInput] = useState("");
  const [status, setStatus] = useState("Ready");
  const [inspectorTab, setInspectorTab] = useState<"node" | "execution">("execution");
  const [execution, setExecution] = useState<ExecutionResponse | null>(null);
  const [copiedLabel, setCopiedLabel] = useState<string>("");
  const [toolCatalog, setToolCatalog] = useState<ToolCatalogItem[]>([]);
  const [agentDefaults, setAgentDefaults] = useState<AgentConfig>(fallbackAgentDefaults);
  const [agentSteps, setAgentSteps] = useState<AgentStep[]>(fallbackAgentSteps);
  const [lastSavedAt, setLastSavedAt] = useState<string>("");

  useEffect(() => {
    Promise.all([
      fetch(`${API_BASE}/node-catalog`),
      fetch(`${API_BASE}/config`),
      fetch(`${API_BASE}/tool-catalog`),
    ])
      .then(async ([catalogRes, configRes, toolsRes]) => {
        if (!catalogRes.ok) {
          throw new Error("Failed to fetch node catalog");
        }
        const catalogData = (await catalogRes.json()) as NodeCatalogItem[];
        setCatalog(catalogData);

        if (configRes.ok) {
          const configData = (await configRes.json()) as AppConfigResponse;
          setAgentDefaults(configData.agent_defaults);
          const configuredSteps = normalizeAgentSteps(configData.multi_agent_defaults?.agents);
          if (configuredSteps.length > 0) {
            setAgentSteps([configuredSteps[0]]);
          }
        }

        if (toolsRes.ok) {
          const toolsData = (await toolsRes.json()) as ToolCatalogItem[];
          setToolCatalog(toolsData);
        }
      })
      .catch((err: Error) => setStatus(`Config error: ${err.message}`));
  }, []);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge({ ...connection, animated: true }, eds));
      if (connection.target) {
        const targetNode = nodes.find((n) => n.id === connection.target);
        if (targetNode?.data.type === "langgraph_agent") {
          setSelectedNodeId(targetNode.id);
          setInspectorTab("node");
        }
      }
    },
    [setEdges, nodes]
  );

  const selectedNode = useMemo(
    () => nodes.find((n) => n.id === selectedNodeId) ?? null,
    [nodes, selectedNodeId]
  );

  const addNode = (type: string) => {
    const id = `n${nodes.length + 1}`;
    const x = 140 + nodes.length * 40;
    const y = 120 + nodes.length * 30;

    const defaultNodeParams = buildDefaultNodeParams(agentDefaults, agentSteps);
    const next: Node<WorkflowNodeData> = {
      id,
      position: { x, y },
      data: {
        label: `${type} ${nodes.length}`,
        type,
        params: structuredClone(defaultNodeParams[type] ?? {}),
      },
    };

    setNodes((curr) => [...curr, next]);
    setSelectedNodeId(id);
    setInspectorTab(type === "langgraph_agent" ? "node" : "execution");
  };

  const updateSelectedParam = (raw: string) => {
    if (!selectedNode) return;

    try {
      const parsed = JSON.parse(raw) as Record<string, unknown>;
      setNodes((curr) =>
        curr.map((node) =>
          node.id === selectedNode.id
            ? { ...node, data: { ...node.data, params: parsed } }
            : node
        )
      );
      setStatus(`Updated params for ${selectedNode.id}`);
    } catch {
      setStatus("Invalid JSON for params");
    }
  };

  const updateSelectedAgentSteps = (agents: AgentStep[]) => {
    if (!selectedNode || selectedNode.data.type !== "langgraph_agent") return;
    setNodes((curr) =>
      curr.map((node) =>
        node.id === selectedNode.id
          ? {
              ...node,
              data: {
                ...node.data,
                params: {
                  ...node.data.params,
                  agents,
                },
              },
            }
          : node
      )
    );
    setStatus(`Updated agent chain for ${selectedNode.id}`);
  };

  const updateSelectedAgentStepField = (
    index: number,
    key: "name" | "system_prompt",
    value: string
  ) => {
    const next = selectedAgentSteps.map((agent, i) =>
      i === index ? { ...agent, [key]: value } : agent
    );
    updateSelectedAgentSteps(next);
  };

  const toggleSelectedAgentStepTool = (index: number, toolName: string, enabled: boolean) => {
    const next = selectedAgentSteps.map((agent, i) => {
      if (i !== index) return agent;
      const nextTools = enabled
        ? Array.from(new Set([...agent.tools, toolName]))
        : agent.tools.filter((tool) => tool !== toolName);
      return { ...agent, tools: nextTools };
    });
    updateSelectedAgentSteps(next);
  };

  const addSelectedAgentStep = () => {
    const next = [
      ...selectedAgentSteps,
      {
        name: `agent_${selectedAgentSteps.length + 1}`,
        system_prompt: "New specialist agent prompt.",
        tools: [],
      },
    ];
    updateSelectedAgentSteps(next);
  };

  const removeSelectedAgentStep = (index: number) => {
    if (selectedAgentSteps.length <= 1) {
      setStatus("At least one agent is required.");
      return;
    }
    const next = selectedAgentSteps.filter((_, i) => i !== index);
    updateSelectedAgentSteps(next);
  };

  const moveSelectedAgentStep = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= selectedAgentSteps.length) return;
    const next = [...selectedAgentSteps];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item);
    updateSelectedAgentSteps(next);
  };

  const buildWorkflowPayload = (): WorkflowPayload => {
    const edgeMap: Record<string, string[]> = {};
    edges.forEach((edge) => {
      if (!edge.source || !edge.target) return;
      edgeMap[edge.source] = edgeMap[edge.source] ?? [];
      edgeMap[edge.source].push(edge.target);
    });

    return {
      id: workflowId,
      name: workflowName,
      nodes: nodes.map((node) => ({
        id: node.id,
        type: node.data.type,
        params: node.data.params,
      })),
      edges: edgeMap,
      active: true,
    };
  };

  const saveWorkflow = async (quiet = false): Promise<boolean> => {
    const payload = buildWorkflowPayload();
    const res = await fetch(`${API_BASE}/workflows`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      const text = await res.text();
      if (res.status === 409) {
        const updateRes = await fetch(`${API_BASE}/workflows/${workflowId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        if (!updateRes.ok) {
          const updateText = await updateRes.text();
          setStatus(`Save failed: ${updateText}`);
          return false;
        }
      } else {
        setStatus(`Save failed: ${text}`);
        return false;
      }
    }

    if (!quiet) {
      setStatus(`Saved workflow ${workflowId}`);
    }
    setLastSavedAt(new Date().toLocaleTimeString());
    return true;
  };

  const runWorkflow = async () => {
    const message = runInput.trim();
    if (!message) {
      setStatus("Please enter a message.");
      return;
    }
    const inputField = agentDefaults.input_field ?? "message";
    const parsedInput: Record<string, unknown> = { [inputField]: message };

    setStatus("Auto-saving workflow before run...");
    const saved = await saveWorkflow(true);
    if (!saved) {
      return;
    }

    const res = await fetch(`${API_BASE}/workflows/${workflowId}/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ input_data: parsedInput }),
    });

    const body = await res.text();
    if (!res.ok) {
      setStatus(`Run failed: ${body}`);
      setExecution(null);
      return;
    }

    try {
      const parsed = JSON.parse(body) as ExecutionResponse;
      setExecution(parsed);
      setStatus(`Run completed (${parsed.status})`);
    } catch {
      setExecution(null);
      setStatus("Run completed, but response parsing failed");
    }
  };

  const copyToClipboard = async (label: string, value: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setCopiedLabel(label);
      window.setTimeout(() => setCopiedLabel(""), 1200);
    } catch {
      setStatus("Clipboard copy failed");
    }
  };

  const userMessage =
    execution && typeof execution.result?.message === "string" ? execution.result.message : null;
  const agentMessage =
    execution && typeof execution.result?.agent_output === "string"
      ? execution.result.agent_output
      : null;
  const selectedAgentSteps =
    selectedNode && selectedNode.data.type === "langgraph_agent"
      ? normalizeAgentSteps(selectedNode.data.params.agents)
      : [];

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">OpenFlow</div>
        <div className="topbar-fields">
          <input
            className="topbar-input topbar-input-id"
            value={workflowId}
            onChange={(e) => setWorkflowId(e.target.value)}
            placeholder="Workflow ID"
          />
          <input
            className="topbar-input"
            value={workflowName}
            onChange={(e) => setWorkflowName(e.target.value)}
            placeholder="Workflow Name"
          />
        </div>
        <div className="topbar-actions">
          <span className="save-stamp">{lastSavedAt ? `Last saved: ${lastSavedAt}` : "Not saved yet"}</span>
          <button onClick={saveWorkflow}>Save</button>
          <button className="primary" onClick={runWorkflow}>
            Execute Workflow
          </button>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <h2>Nodes</h2>
          <div className="palette">
            {catalog
              .filter((item) => item.type !== "template" && item.type !== "multi_agent")
              .map((item) => (
                <button key={item.type} onClick={() => addNode(item.type)} title={item.description}>
                  + {item.type}
                </button>
              ))}
          </div>
        </aside>

        <main className="canvas">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_, node) => {
              setSelectedNodeId(node.id);
              setInspectorTab(node.data.type === "langgraph_agent" ? "node" : "execution");
            }}
            fitView
          >
            <MiniMap />
            <Controls />
            <Background />
          </ReactFlow>
          <div className="canvas-status">{status}</div>
        </main>

        <aside className="inspector">
        <div className="inspector-tabs">
          <button
            className={inspectorTab === "node" ? "tab-active" : ""}
            onClick={() => setInspectorTab("node")}
          >
            Node
          </button>
          <button
            className={inspectorTab === "execution" ? "tab-active" : ""}
            onClick={() => setInspectorTab("execution")}
          >
            Execution
          </button>
        </div>

        {inspectorTab === "node" ? (
          <>
            <h2>Node Inspector</h2>
            {selectedNode ? (
              <>
                {selectedNode.data.type === "langgraph_agent" ? (
                  <>
                    <label>Agents</label>
                    <div className="agent-editor-list">
                      {selectedAgentSteps.map((agent, index) => (
                        <div className="agent-editor-card" key={`${agent.name}-${index}`}>
                          <div className="agent-editor-head">
                            <strong>Agent {index + 1}</strong>
                            <div className="agent-editor-actions">
                              <button onClick={() => moveSelectedAgentStep(index, -1)}>Up</button>
                              <button onClick={() => moveSelectedAgentStep(index, 1)}>Down</button>
                              <button onClick={() => removeSelectedAgentStep(index)}>Remove</button>
                            </div>
                          </div>
                          <label>Name</label>
                          <input
                            value={agent.name}
                            onChange={(e) => updateSelectedAgentStepField(index, "name", e.target.value)}
                          />
                          <label>System Prompt</label>
                          <textarea
                            rows={3}
                            value={agent.system_prompt}
                            onChange={(e) =>
                              updateSelectedAgentStepField(index, "system_prompt", e.target.value)
                            }
                          />
                          <label>Tools</label>
                          <div className="tool-toggle-list">
                            {toolCatalog.map((tool) => (
                              <label className="tool-toggle-row" key={`${index}-${tool.name}`} title={tool.description}>
                                <input
                                  type="checkbox"
                                  checked={agent.tools.includes(tool.name)}
                                  onChange={(e) =>
                                    toggleSelectedAgentStepTool(index, tool.name, e.target.checked)
                                  }
                                />
                                <span>{tool.name}</span>
                              </label>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                    <button onClick={addSelectedAgentStep}>Add Agent</button>
                  </>
                ) : null}
                <details className="advanced-json">
                  <summary>Advanced: Params (JSON)</summary>
                  <textarea
                    className="params-json"
                    rows={8}
                    defaultValue={JSON.stringify(selectedNode.data.params, null, 2)}
                    onBlur={(e) => updateSelectedParam(e.target.value)}
                    key={selectedNode.id}
                  />
                </details>
              </>
            ) : (
              <p className="muted">Select a node to edit parameters.</p>
            )}
          </>
        ) : (
          <>
            <h2>Execution</h2>
            <textarea
              value={runInput}
              onChange={(e) => setRunInput(e.target.value)}
              rows={3}
              placeholder="Prompt here..."
            />
            {execution ? (
              <div className="execution-card">
                <p>
                  <strong>Execution ID:</strong> {execution.id}
                </p>
                <p>
                  <strong>Status:</strong>{" "}
                  <span className={execution.status === "success" ? "status-ok" : "status-bad"}>
                    {execution.status}
                  </span>
                </p>
                <label>Conversation</label>
                <div className="chat-panel">
                  <div className="bubble bubble-user">
                    <div className="bubble-head">
                      <strong>You</strong>
                      <button
                        className="copy-btn"
                        onClick={() => copyToClipboard("user", userMessage ?? "")}
                        disabled={!userMessage}
                      >
                        {copiedLabel === "user" ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <p>{userMessage ?? "No input message field found in result."}</p>
                  </div>
                  <div className="bubble bubble-agent">
                    <div className="bubble-head">
                      <strong>Agent</strong>
                      <button
                        className="copy-btn"
                        onClick={() => copyToClipboard("agent", agentMessage ?? "")}
                        disabled={!agentMessage}
                      >
                        {copiedLabel === "agent" ? "Copied" : "Copy"}
                      </button>
                    </div>
                    <p>{agentMessage ?? "No agent output field found in result."}</p>
                  </div>
                </div>
                <details className="advanced-json" open={false}>
                  <summary>Raw Result (JSON)</summary>
                  <pre className="raw-json">{JSON.stringify(execution.result, null, 2)}</pre>
                </details>
                {execution.error ? (
                  <>
                    <label>Error</label>
                    <pre>{execution.error}</pre>
                  </>
                ) : null}
              </div>
            ) : (
              <p className="muted">Run a workflow to see execution results here.</p>
            )}
          </>
        )}
        </aside>
      </div>
    </div>
  );
}
