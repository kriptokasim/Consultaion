export interface MockAgent {
    id: string
    name: string
    model: string
    provider: string
    role: 'debater' | 'judge' | 'synthesizer'
}

export interface MockArgument {
    agentId: string
    agentName: string
    content: string
}

export interface MockRound {
    number: number
    title: string
    arguments: MockArgument[]
}

export interface MockJudgeComment {
    judge: string
    comment: string
    leaning: string
}

export interface MockChampion {
    winner: string
    winnerModel: string
    synthesis: string
    reasoning: string
}

export interface MockDebateData {
    question: string
    context: string
    agents: MockAgent[]
    rounds: MockRound[]
    judgeCommentary: MockJudgeComment[]
    championAnswer: MockChampion
}

export const MOCK_DEBATE: MockDebateData = {
    question: "How should a mid-size SaaS company approach AI rollout in 2025?",
    context: "A Series B SaaS company (150 employees, $20M ARR) wants to integrate AI into their product and internal operations without overwhelming the team or customers.",

    agents: [
        {
            id: "gpt4o",
            name: "Strategic Planner",
            model: "GPT-4o",
            provider: "OpenAI",
            role: "debater"
        },
        {
            id: "claude",
            name: "Risk Assessor",
            model: "Claude 3.5 Sonnet",
            provider: "Anthropic",
            role: "debater"
        },
        {
            id: "gemini",
            name: "Research Analyst",
            model: "Gemini Pro",
            provider: "Google",
            role: "debater"
        }
    ],

    rounds: [
        {
            number: 1,
            title: "Opening Statements",
            arguments: [
                {
                    agentId: "gpt4o",
                    agentName: "Strategic Planner",
                    content: "Start with low-hanging fruit: customer support automation and internal knowledge management. Deploy AI copilots for support tickets first—this shows immediate ROI, builds team confidence, and creates a feedback loop. Then expand to product features incrementally. Key: ship fast, measure impact, iterate weekly."
                },
                {
                    agentId: "claude",
                    agentName: "Risk Assessor",
                    content: "Prioritize safety and customer trust over speed. Begin with a 90-day pilot using AI internally only—support team, sales enablement, engineering docs. Gather lessons learned, establish governance policies, and create an AI ethics framework. Only then roll out customer-facing features with opt-in controls and transparent communication."
                },
                {
                    agentId: "gemini",
                    agentName: "Research Analyst",
                    content: "Conduct a comprehensive AI readiness audit first. Survey your 150 employees about pain points, analyze competitor AI features, and map customer workflow bottlenecks. This data-driven approach prevents premature optimization. Then create a tiered rollout: Tier 1 (internal efficiency), Tier 2 (beta customer features), Tier 3 (general availability)."
                }
            ]
        },
        {
            number: 2,
            title: "Rebuttal & Refinement",
            arguments: [
                {
                    agentId: "gpt4o",
                    agentName: "Strategic Planner",
                    content: "I agree with the audit concept from Research Analyst, but compress it to 2 weeks max—analysis paralysis is real at Series B stage. Risk Assessor's 90-day internal pilot is wise, but pair it with immediate quick wins. Run support automation AND governance building in parallel, not sequentially. Time is a competitive advantage here."
                },
                {
                    agentId: "claude",
                    agentName: "Risk Assessor",
                    content: "Strategic Planner's urgency is noted, but consider the reputational cost of a public AI failure at $20M ARR—you cannot afford customer churn from buggy AI features. I propose a hybrid: 30-day internal pilot with clear success metrics, THEN controlled beta with 10-15 friendly customers who've opted in. This balances speed with safety."
                },
                {
                    agentId: "gemini",
                    agentName: "Research Analyst",
                    content: "Both valid points. Let me add: dedicate 1 'AI lead' internally—someone technical who can own evaluation, integration, and measurement. Without ownership, this becomes vaporware. Also, set aside $50-100K budget for tooling/APIs upfront. Half-hearted AI rollouts with inadequate resources fail. Commit properly or don't start."
                }
            ]
        }
    ],

    judgeCommentary: [
        {
            judge: "Judge GPT-4o",
            comment: "All three agents identified critical execution elements, but Risk Assessor (Claude) provided the strongest framework for balancing speed with customer trust—a crucial factor at Series B. The 30-day internal pilot + controlled beta approach is pragmatic.",
            leaning: "Claude (Risk Assessor)"
        },
        {
            judge: "Judge Claude",
            comment: "Research Analyst (Gemini) made an often-overlooked point: dedicate ownership and budget. Without these, AI rollouts stall. Strategic Planner's urgency is important, but the structured approach from Risk Assessor combined with Gemini's resource allocation is most complete.",
            leaning: "Tie: Claude & Gemini"
        },
        {
            judge: "Judge Gemini",
            comment: "Strategic Planner (GPT-4o) correctly identified the risk of analysis paralysis, which plagues mid-size companies. However, Risk Assessor's emphasis on customer trust and controlled rollout shows deeper understanding of Series B stakes. The hybrid approach scores highest.",
            leaning: "Claude (Risk Assessor)"
        }
    ],

    championAnswer: {
        winner: "Risk Assessor",
        winnerModel: "Claude 3.5 Sonnet",
        synthesis: "A mid-size SaaS company should execute a **phased AI rollout with clear governance**: (1) **Week 1-2**: Conduct rapid AI readiness audit (team survey + competitor analysis). (2) **Week 3-6**: 30-day internal pilot focusing on support automation and knowledge management, with dedicated AI lead and $75K initial budget. (3) **Week 7-10**: Controlled beta with 10-15 opted-in customers for one product feature. (4) **Week 11+**: Iterate based on feedback, expand gradually. This balances urgency with risk management—critical for protecting customer trust at $20M ARR while maintaining competitive velocity.",
        reasoning: "Claude's Risk Assessor persona won by emphasizing customer trust and measured rollout, which resonated most with the judging panel given the Series B context. However, the champion synthesis integrates the best elements from all three: GPT-4o's bias for speed, Claude's governance framework, and Gemini's resource allocation insight."
    }
}
