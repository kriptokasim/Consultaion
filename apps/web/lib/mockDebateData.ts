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

export MockJudgeComment {
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

export interface DemoScenario {
    id: string
    title: string
    shortDescription: string
    tag: string
    data: MockDebateData
}

// Scenario 1: SaaS AI Rollout (migrated from original MOCK_DEBATE)
const saasRolloutScenario: DemoScenario = {
    id: "saas-rollout",
    title: "AI Rollout Strategy",
    shortDescription: "Mid-size SaaS deciding how to adopt AI in 2025",
    tag: "Strategy",
    data: {
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
}

// Scenario 2: Bank AI Governance
const bankGovernanceScenario: DemoScenario = {
    id: "bank-governance",
    title: "Enterprise AI Governance",
    shortDescription: "Regulated bank evaluating AI compliance framework",
    tag: "Risk & Governance",
    data: {
        question: "How should a regional bank adopt AI while meeting regulatory requirements?",
        context: "A $5B asset regional bank must balance AI innovation with GDPR, Basel III capital requirements, and internal audit/compliance frameworks. Board wants AI roadmap that satisfies regulators.",

        agents: [
            {
                id: "claude",
                name: "Compliance Officer",
                model: "Claude 3.5 Sonnet",
                provider: "Anthropic",
                role: "debater"
            },
            {
                id: "gemini",
                name: "Technology Strategist",
                model: "Gemini Pro",
                provider: "Google",
                role: "debater"
            },
            {
                id: "gpt4o",
                name: "Risk Manager",
                model: "GPT-4o",
                provider: "OpenAI",
                role: "debater"
            }
        ],

        rounds: [
            {
                number: 1,
                title: "Opening Statements",
                arguments: [
                    {
                        agentId: "claude",
                        agentName: "Compliance Officer",
                        content: "Establish a formal AI Governance Committee first—CISO, CRO, Chief Compliance Officer, and Board representation. Create a three-tier model approval process: Tier 1 (low-risk internal tools), Tier 2 (customer-facing with human oversight), Tier 3 (high-impact decisions requiring full board approval). Document every decision with audit trails. This satisfies Basel III operational risk requirements and GDPR Article 22."
                    },
                    {
                        agentId: "gemini",
                        agentName: "Technology Strategist",
                        content: "Start with clear use cases mapped to business value: fraud detection (proven), credit underwriting enhancement (incremental), and customer service chatbots (high visibility). For each, conduct Model Risk Management assessments per SR 11-7 guidance. Implement explainability tools (SHAP, LIME) built into every model. Technology should enable compliance, not fight it."
                    },
                    {
                        agentId: "gpt4o",
                        agentName: "Risk Manager",
                        content: "Quantify the risk of NOT adopting AI—competitors are moving. But de-risk through third-party validation: engage external auditors to review AI models quarterly, purchase cyber insurance specifically covering AI incidents, and create a $2M reserve for potential algorithmic bias lawsuits. Risk management isn't about avoiding AI; it's about controlled deployment with financial backstops."
                    }
                ]
            },
            {
                number: 2,
                title: "Rebuttal & Refinement",
                arguments: [
                    {
                        agentId: "claude",
                        agentName: "Compliance Officer",
                        content: "Technology Strategist's emphasis on explainability is critical—regulators will ask 'how did the model decide?' Risk Manager's third-party validation is excellent, but I'd add: require continuous monitoring dashboards showing model drift, bias metrics, and fairness KPIs. These should feed directly into quarterly board risk reports."
                    },
                    {
                        agentId: "gemini",
                        agentName: "Technology Strategist",
                        content: "Compliance Officer's governance structure is solid, but don't create analysis paralysis. I propose 'AI sprints': 6-week cycles where one use case is fully evaluated (tech + compliance + risk). This maintains regulatory rigor while showing progress to the board. Also: invest in a centralized AI platform (e.g., Databricks, Dataiku) for consistent governance tooling."
                    },
                    {
                        agentId: "gpt4o",
                        agentName: "Risk Manager",
                        content: "Both perspectives are valid. Let me add financial structure: allocate 15% of AI budget to compliance/risk activities upfront—not as afterthought. This includes legal reviews, fairness testing, and third-party audits. Also, create 'AI incident response playbook' before first deployment. Banks are held to higher standards; we must be prepared for regulatory scrutiny from day one."
                    }
                ]
            }
        ],

        judgeCommentary: [
            {
                judge: "Judge GPT-4o",
                comment: "All three agents demonstrated deep understanding of regulatory landscape. Compliance Officer (Claude) provided the most thorough governance framework, which is table-stakes for a regulated institution. The three-tier approval model is particularly well-suited for banking.",
                leaning: "Claude (Compliance Officer)"
            },
            {
                judge: "Judge Claude",
                comment: "Technology Strategist (Gemini) correctly identified that governance without momentum creates stagnation. The 'AI sprints' concept balances rigor with progress. However, Compliance Officer's audit trail emphasis addresses the #1 regulator concern in banking AI.",
                leaning: "Tie: Claude & Gemini"
            },
            {
                judge: "Judge Gemini",
                comment: "Risk Manager (GPT-4o) made a crucial point often missed: quantify the risk of inaction. In banking, competitive disadvantage is also a risk. The 15% compliance budget allocation is realistic and shows maturity. Strong synthesis of business case with regulatory adherence.",
                leaning: "GPT-4o (Risk Manager)"
            }
        ],

        championAnswer: {
            winner: "Compliance Officer",
            winnerModel: "Claude 3.5 Sonnet",
            synthesis: "A regional bank should adopt AI through a **structured, auditable governance framework**: (1) **Month 1**: Establish AI Governance Committee with CISO, CRO, CCO, Board rep. (2) **Month 2-3**: Implement three-tier model approval process and select centralized AI platform. (3) **Month 4+**: Execute 6-week 'AI sprints' for fraud detection, credit underwriting, chatbots—each with full MRM assessment, explainability tools, bias testing, and quarterly external audits. (4) **Ongoing**: Maintain continuous monitoring dashboards, allocate 15% of AI budget to compliance, and prepare incident response playbook. This satisfies Basel III, GDPR, and SR 11-7 while demonstrating measurable progress to board and regulators.",
            reasoning: "Claude's Compliance Officer won by providing the most comprehensive regulatory framework, which is the primary concern for a $5B bank. However, the champion synthesis integrates Gemini's 'AI sprints' for momentum and GPT-4o's financial risk quantification, creating a balanced approach that satisfies both regulators and business objectives."
        }
    }
}

// Scenario 3: Product Roadmap
const productRoadmapScenario: DemoScenario = {
    id: "product-roadmap",
    title: "Feature Prioritization",
    shortDescription: "Product team deciding Q2 roadmap priorities",
    tag: "Product",
    data: {
        question: "Which features should we prioritize for Q2: advanced analytics, mobile redesign, or API platform?",
        context: "A B2B SaaS product team (8 engineers, 2 designers) must choose between three major initiatives for Q2. Current product has 500 paying customers, $3M ARR, 15% monthly churn (too high).",

        agents: [
            {
                id: "gemini",
                name: "Data Analyst",
                model: "Gemini Pro",
                provider: "Google",
                role: "debater"
            },
            {
                id: "gpt4o",
                name: "Product Manager",
                model: "GPT-4o",
                provider: "OpenAI",
                role: "debater"
            },
            {
                id: "claude",
                name: "Engineering Lead",
                model: "Claude 3.5 Sonnet",
                provider: "Anthropic",
                role: "debater"
            }
        ],

        rounds: [
            {
                number: 1,
                title: "Opening Statements",
                arguments: [
                    {
                        agentId: "gemini",
                        agentName: "Data Analyst",
                        content: "Advanced analytics is the clear winner. Customer exit surveys show #1 churn reason is 'lack of reporting flexibility'—mentioned by 64% of churned users. Current dashboards are basic. If we ship customizable dashboards, drill-downs, and data exports in Q2, we directly address our biggest retention problem. This could reduce churn from 15% to sub-10%, which compounds over time."
                    },
                    {
                        agentId: "gpt4o",
                        agentName: "Product Manager",
                        content: "I disagree—mobile redesign should be #1. We have 0 mobile optimization currently, yet 40% of user sessions are on mobile (terrible UX). This is a market expansion play: competitors are mobile-first. If we don't ship responsive mobile in Q2, we lose enterprise deals where buyer committees use our product on iPads during meetings. Analytics won't matter if we can't demo well on mobile."
                    },
                    {
                        agentId: "claude",
                        agentName: "Engineering Lead",
                        content: "API platform is the strategic choice. Both analytics and mobile are feature requests, but API is a *business model* unlock. With a public API, we enable integrations, partnerships, developer ecosystem, and potential marketplace revenue. This 3x's our addressable market. Yes, it's technically complex, but with 8 engineers, we can ship a v1 API in Q2 and iterate. Think long-term leverage, not short-term fixes."
                    }
                ]
            },
            {
                number: 2,
                title: "Rebuttal & Refinement",
                arguments: [
                    {
                        agentId: "gemini",
                        agentName: "Data Analyst",
                        content: "Product Manager makes a fair point about mobile, but here's the nuance: our user persona is 'data-driven operations manager'—desktop-heavy workflow. Mobile is nice-to-have for them, not critical path. Engineering Lead's API vision is exciting long-term, but we're at $3M ARR with 15% churn—we must stop the bleeding NOW. Analytics directly solves retention, which is more valuable than new customer acquisition at our stage."
                    },
                    {
                        agentId: "gpt4o",
                        agentName: "Product Manager",
                        content: "Data Analyst's churn data is compelling, I'll concede that. But what if we do a hybrid: ship 'analytics lite' (3-4 pre-built report templates, not full customization) PLUS basic mobile responsiveness in Q2? This covers retention AND expansion. Engineering Lead's API is a 6-month project minimum—too risky for a single-quarter bet with our team size."
                    },
                    {
                        agentId: "claude",
                        agentName: "Engineering Lead",
                        content: "Product Manager's hybrid is pragmatic, but risks doing two things poorly instead of one thing great. Here's my counter: what if we do analytics in Q2 (addresses churn), but architect it API-first internally? This gives us the analytics win NOW while laying foundation for public API in Q3-Q4. We get retention fix immediately and strategic platform play with slightly delayed timeline. Best of both worlds."
                    }
                ]
            }
        ],

        judgeCommentary: [
            {
                judge: "Judge GPT-4o",
                comment: "Data Analyst (Gemini) brought the most concrete evidence—64% of churned users cited reporting as the reason. At 15% monthly churn, this is an existential issue. Engineering Lead's API vision is sound long-term, but Data Analyst correctly prioritized survival over growth.",
                leaning: "Gemini (Data Analyst)"
            },
            {
                judge: "Judge Claude",
                comment: "Product Manager (GPT-4o) identified a real gap (mobile UX), but Data Analyst's churn analysis trumps it. However, Engineering Lead's 'API-first architecture' synthesis is brilliant—you can build analytics in a way that enables the API later without extra work. This is systems thinking.",
                leaning: "Tie: Gemini & Claude"
            },
            {
                judge: "Judge Gemini",
                comment: "All three made data-driven arguments. Data Analyst wins on prioritization—at $3M ARR with 15% churn, retention is life-or-death. Mobile can wait one quarter. API is important but Engineering Lead's own timeline admission (6 months minimum) disqualifies it for Q2. Analytics is the right call.",
                leaning: "Gemini (Data Analyst)"
            }
        ],

        championAnswer: {
            winner: "Data Analyst",
            winnerModel: "Gemini Pro",
            synthesis: "The product team should **prioritize advanced analytics for Q2** to address the critical 15% churn rate. Specifically: (1) **Weeks 1-4**: Ship 5 customizable dashboard templates targeting the top churn reasons. (2) **Weeks 5-8**: Add drill-down capabilities and CSV/Excel export. (3) **Weeks 9-12**: Implement saved report functionality and email scheduling. **Key insight from Engineering Lead**: Build all analytics features with API-first architecture internally, even though the public API won't launch until Q3/Q4. This solves the immediate retention crisis (projected to reduce churn to 10-12%) while laying groundwork for the strategic API platform. Mobile redesign moves to Q3 roadmap. With 500 customers and $3M ARR, stopping churn is more valuable than new feature expansion.",
            reasoning: "Gemini's Data Analyst won by presenting the strongest quantitative case (64% churn correlation) and correctly diagnosing that retention at this stage is existential. The champion synthesis incorporates Claude's 'API-first architecture' insight, which is a force-multiplier that doesn't sacrifice the immediate churn fix. GPT-4o's mobile concerns are valid but deprioritized to Q3."
        }
    }
}

export const DEMO_SCENARIOS: DemoScenario[] = [
    saasRolloutScenario,
    bankGovernanceScenario,
    productRoadmapScenario
]

// Backward compatibility: export first scenario as default
export const MOCK_DEBATE: MockDebateData = DEMO_SCENARIOS[0].data
