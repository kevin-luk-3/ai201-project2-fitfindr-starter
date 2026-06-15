Project 2: FitFindr
Total Points: 25pts + 7pts bonus

Required Features
4pts	Three Tools with Defined Interfaces
1	README lists all 3 required tools, each with a named function.
1	Each tool's inputs are described with parameter names and types (e.g., "description (str), size (str), max_price (float)").
1	Each tool's return value is described — not just "returns a list," but what's in the list.
1	Demo or source shows all 3 tools being called within a single interaction.
2pts	Multi-Step Workflow End to End
1	Demo or source shows a complete interaction that starts with a natural language user query and ends with a fit card, using all 3 required tools along the way.
1	The demo narration or the README / planning.md walkthrough explains what the agent is doing at each step — which tool is being called and why.
3pts	State Management Across Tool Calls
1	Demo or source shows that the item returned by search_listings is the same item passed into suggest_outfit — without the user re-entering it.
1	Demo or source shows the outfit from suggest_outfit passing into create_fit_card without re-entry.
1	README describes the state management approach: what is stored, when, and how it passes between tools.
4pts	Planning Loop Adaptiveness
1	README explains the planning loop's conditional logic — what state it checks and what triggers each decision. "It decides what to do next" does not earn this point.
1	README describes what the agent does specifically when search_listings returns no results (not just "it handles errors").
2	Demo or source shows the agent behaving differently for a non-standard input compared to the happy path — the agent doesn't call all tools unconditionally in the same sequence.
3pts	Error Handling
1	README describes the specific failure mode for each of the 3 required tools and what the agent does in each case.
1	Demo or source shows handling for at least one deliberately triggered failure (not a happy-path edge case — an actual failure).
1	Demo or source shows the agent's response to the failure is specific and actionable — it tells the user what failed and what to try next.
4pts	planning.md Quality
1	Tools — all 3 required tools described with name, inputs (name + type), return value, and what the agent does on failure.
1	Planning Loop — conditional logic described (not just intent); State Management — what is stored and how it flows.
1	Error Handling table — completed with specific agent responses for each tool's failure mode; Complete Interaction walkthrough — traces the example query step-by-step through all three tool calls.
1	Architecture diagram — shows data and control flow through the agent; AI Tool Plan — names specific spec sections used to prompt AI tools and describes how generated code was verified against the spec.
3pts	README Completeness
1	Tool inventory with inputs, outputs, and purpose for each tool; planning loop explanation with conditional logic; state management approach.
1	Error handling per tool with at least one concrete example from testing.
1	Spec reflection (one way the spec helped, one divergence and why).
2pts	AI Usage Transparency
1	Section describes at least 2 specific instances of AI tool use, naming what the student directed the AI to do in each case.
1	Each instance describes what the student reviewed, revised, or overrode.
