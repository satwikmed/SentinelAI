# Comparative notes: LangGraph vs CrewAI for SentinelAI-style orchestration
# This is an evaluation notebook (markdown + runnable snippets), not a production path.

"""Framework comparison for enterprise AI gateway orchestration.

Run snippets independently if packages are installed:

  pip install langgraph crewai

Conclusion used by SentinelAI:
  LangGraph won for typed state, explicit edges (planner-executor + reflection),
  and first-class checkpointing — critical for auditability.
  CrewAI is strong for role-based agent crews with less graph control.
"""

COMPARISON = """
| Criterion              | LangGraph                         | CrewAI                            |
|------------------------|-----------------------------------|-----------------------------------|
| Orchestration model    | Explicit state graph + edges      | Role/crew task delegation         |
| Typed persisted state  | First-class (TypedDict + checkpointer) | Limited / app-managed          |
| Reflection loops       | Conditional edges (native)        | Possible via task retry patterns  |
| Multi-provider routing | Bring your own (our adapters)     | Bring your own                    |
| Enterprise audit story | Strong (inspectable checkpoints)  | Weaker without custom logging     |
| Learning curve         | Medium                            | Lower for simple crews            |

Decision: production path = LangGraph. CrewAI kept as breadth experiment only.
"""

print(COMPARISON)

# --- LangGraph sketch (mirrors production graph) ---
LANGGRAPH_SKETCH = '''
from typing import TypedDict
from langgraph.graph import StateGraph, END

class State(TypedDict):
    query: str
    draft: str
    needs_revision: bool

def planner(s): ...
def executor(s): ...
def verifier(s): ...

g = StateGraph(State)
g.add_node("planner", planner)
g.add_node("executor", executor)
g.add_node("verifier", verifier)
g.set_entry_point("planner")
g.add_edge("planner", "executor")
g.add_edge("executor", "verifier")
g.add_conditional_edges("verifier", lambda s: "executor" if s["needs_revision"] else END)
'''

# --- CrewAI sketch (experiment only) ---
CREWAI_SKETCH = '''
from crewai import Agent, Task, Crew

planner = Agent(role="Planner", goal="Decompose requests", backstory="...")
executor = Agent(role="Executor", goal="Answer with tools", backstory="...")
verifier = Agent(role="Verifier", goal="Check faithfulness", backstory="...")

tasks = [
  Task(description="Plan steps for: {query}", agent=planner),
  Task(description="Execute plan", agent=executor),
  Task(description="Verify answer", agent=verifier),
]
crew = Crew(agents=[planner, executor, verifier], tasks=tasks)
# result = crew.kickoff(inputs={"query": "..."})
'''

print("LangGraph sketch:\\n", LANGGRAPH_SKETCH)
print("CrewAI sketch:\\n", CREWAI_SKETCH)
