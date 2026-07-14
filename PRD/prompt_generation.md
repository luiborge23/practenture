# BizSimAI Prompt Generation Output

Based on the SOTA research and deep analysis, here are the structured prompts with guardrails for BizSimAI development:

## Core System Prompts

### 1. Simulation Engine Prompt
"You are designing a deterministic business simulation engine that processes team decisions in real-time. The engine must:
- Accept functional area decisions (marketing, production, finance, R&D) from multiple teams
- Calculate immediate market impacts based on supply/demand dynamics
- Update financial statements, market share, and competitive positioning instantly
- Ensure reproducibility for grading and fairness
- Include guardrails: sanitize all inputs, prevent arbitrary code execution, validate decision boundaries"

### 2. Professor Console Prompt
"You are designing a real-time professor dashboard for BizSimAI that enables coaching rather than administration. The console must:
- Provide live visibility into all team decisions and performance metrics
- Offer one-click intervention tools (pause, highlight, announce)
- Generate adaptive difficulty suggestions based on class performance
- Include guardrails: prevent manipulation of ongoing simulations, ensure student data privacy, validate professor permissions"

### 3. Student Team Interface Prompt
"You are designing an intuitive student team interface for BizSimAI that supports strategic decision-making. The interface must:
- Present functional area decisions in an accessible format
- Show real-time impact of decisions on financials and market position
- Display competitor intelligence with appropriate delays/limitations
- Support hypothesis testing and strategy iteration
- Include guardrails: prevent unrealistic decision combinations, validate against budget constraints, ensure equal access to information"

### 4. Adaptive Learning System Prompt
"You are designing an AI-powered adaptation system for BizSimAI that personalizes the learning experience. The system must:
- Analyze team decision patterns and performance metrics
- Adjust market volatility, competitor behavior, and complexity in real-time
- Generate personalized feedback and learning recommendations
- Maintain educational integrity while adapting challenges
- Include guardrails: prevent unfair advantage/disadvantage, ensure adaptation aligns with learning objectives, maintain transparency about adaptations"

### 5. Assessment & Analytics Prompt
"You are designing a comprehensive assessment system for BizSimAI that maps to educational standards. The system must:
- Track decision quality, strategic thinking, and financial literacy competencies
- Generate reports aligned with AACSB/ABET standards
- Provide actionable insights for both professors and students
- Support longitudinal learning tracking across multiple sessions
- Include guardrails: ensure assessment validity, prevent gaming of metrics, maintain student privacy"

## Input Sanitization Guardrails (to be included in all prompts)
- All user inputs must be validated against expected ranges and types
- No arbitrary code execution or system commands allowed
- Decision values must be constrained to realistic business limits
- File uploads (if any) must be restricted to safe formats and sizes
- Authentication tokens must be validated and expired appropriately
- All database queries must use parameterized statements to prevent injection

## Output Formatting Guardrails
- All API responses must follow consistent JSON structure
- Error messages must be informative but not expose system internals
- Timestamps must be in ISO 8601 format
- Financial values must be formatted with appropriate precision and currency
- Empty or null values must be handled consistently

## Performance Guardrails
- Simulation calculations must complete within 100ms per decision batch
- WebSocket updates must be pushed within 50ms of calculation completion
- Memory usage must be monitored and bounded
- Database queries must be optimized with appropriate indexing
- Caching strategies must be implemented for frequently accessed data

These prompts will guide the implementation of each major subsystem while ensuring safety, consistency, and educational effectiveness.