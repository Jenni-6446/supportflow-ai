import type {
  DemoTicketScenario,
  TicketInput
} from "./types";

interface TicketInfoPanelProps {
  ticket: TicketInput;
  demoTickets: DemoTicketScenario[];
  selectedDemoId: string | null;
  isAnalyzing: boolean;
  error: string | null;
  onTicketChange: (ticket: TicketInput) => void;
  onLoadDemo: (scenario: DemoTicketScenario) => void;
  onAnalyze: () => void;
}

const issueExamples = [
  "I cannot log in to my work account.",
  "My external monitor is black.",
  "I cannot connect to VPN.",
  "Outlook is not receiving emails.",
  "The software update keeps failing."
];

export function TicketInfoPanel({
  ticket,
  demoTickets,
  selectedDemoId,
  isAnalyzing,
  error,
  onTicketChange,
  onLoadDemo,
  onAnalyze
}: TicketInfoPanelProps) {
  const updateField = <TKey extends keyof TicketInput>(
    key: TKey,
    value: TicketInput[TKey]
  ) => {
    onTicketChange({ ...ticket, [key]: value });
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <div>
          <h2 className="panel-title">Describe Issue</h2>
          <p className="panel-subtitle">
            Start with the problem in your own words.
          </p>
        </div>
      </div>
      <div className="panel-body">
        {error ? <div className="alert">{error}</div> : null}
        <div className="intake-flow">
          <div className="field full issue-field">
            <label htmlFor="userMessage">Describe the issue you are experiencing</label>
            <textarea
              id="userMessage"
              value={ticket.userMessage}
              onChange={(event) => updateField("userMessage", event.target.value)}
              placeholder="Tell me what is not working. Include any error message or recent change if you know it."
            />
          </div>

          <details className="try-example">
            <summary>Try an example</summary>
            <div className="example-prompts" aria-label="Example issue prompts">
              {issueExamples.map((example) => (
                <button
                  className="example-prompt"
                  key={example}
                  type="button"
                  onClick={() => updateField("userMessage", example)}
                >
                  {example}
                </button>
              ))}
            </div>
            <div className="field full demo-field">
              <label htmlFor="demoTicket">Demo scenarios</label>
              <select
                id="demoTicket"
                value={selectedDemoId ?? ""}
                onChange={(event) => {
                  const scenario = demoTickets.find(
                    (item) => item.id === event.target.value
                  );
                  if (scenario) {
                    onLoadDemo(scenario);
                  }
                }}
              >
                <option value="">Select a demo ticket</option>
                {demoTickets.map((scenario) => (
                  <option key={scenario.id} value={scenario.id}>
                    {scenario.label}
                  </option>
                ))}
              </select>
              {selectedDemoId ? (
                <span className="field-helper">
                  Loaded demo:{" "}
                  {demoTickets.find((scenario) => scenario.id === selectedDemoId)
                    ?.label ?? selectedDemoId}
                </span>
              ) : null}
            </div>
          </details>
        </div>
        <div className="actions">
          <button
            type="button"
            className="button-primary"
            disabled={isAnalyzing}
            onClick={onAnalyze}
          >
            {isAnalyzing ? "Analyzing..." : "Start Troubleshooting"}
          </button>
        </div>
      </div>
    </section>
  );
}
