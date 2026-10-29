# Topics, clusters and example questions

Each topic is one cluster (one cluster per subject; there is no topic taxonomy inside a cluster in v1). The example questions below are drafts derived from the topic descriptions. Edit them freely: they seed the LeanRAG trial, the gold question set for the tests, and the first agent contexts.

Sources in v1 are arXiv (no key) and OpenAlex (only if the owner supplies a key). Topics 1, 4 and 5 are partly practitioner subjects that live in blogs, documentation and repositories, which v1 does not fetch. For those clusters, add such material as local files with `rkc add-file`.

## First real topic for the manual end-to-end test: 2. Financial markets model evaluation

Chosen because it fits scholarly sources well (arXiv categories such as q-fin.ST, q-fin.CP and stat.ML), has clear vocabulary, and is likely to contain real disagreements (which exercises conflict handling).

## 1. AI engineering  (cluster: `ai-engineering`)
Everything about AI engineering, that is, deploying agents into processes.
1. What failure modes are documented when LLM agents are deployed into production business processes, and how are they mitigated?
2. Which evaluation and monitoring approaches are used for agents running in production workflows?
3. What do studies report about human-in-the-loop designs for agents embedded in enterprise processes?

## 2. Financial markets model evaluation  (cluster: `fin-model-evaluation`)
State of the art of how to evaluate models, for example hyperparameter search, and how to avoid leaks.
1. Which methods are recommended to evaluate trading or forecasting models without backtest overfitting (walk-forward, purged or combinatorial cross-validation, deflated Sharpe ratio)?
2. What causes data leakage in financial machine-learning pipelines, and how do papers propose to detect or prevent it?
3. How should hyperparameter search be done for financial time series, and where do papers disagree?

## 3. Financial markets feature engineering  (cluster: `fin-feature-engineering`)
1. Which feature families (microstructure, alternative data, text, cross-asset) are reported as useful, and under what conditions?
2. How do papers handle feature selection, stationarity and look-ahead bias?
3. Which claims about feature importance in financial models contradict each other?

## 4. Agentic engineering  (cluster: `agentic-engineering`)
Everything on how to best work with agents to create code: best practices, skills, tools, workflows.
1. Which workflows and practices improve code quality when working with coding agents?
2. What evidence exists on the effectiveness of skills, tools and context files for coding agents?
3. Where do studies disagree about the productivity or reliability of coding agents?

## 5. Skills for motivation letters  (cluster: `motivation-letter-skills`)
How to set up skills for an agent to write motivation letters for jobs.
1. What approaches exist for configuring an LLM agent with reusable skills to write tailored application letters?
2. What do studies say about LLM-written cover letters (quality, detectability, bias)?
3. How can an agent personalize a letter from a user's background without fabricating claims?

## Draft arXiv query specs (to be refined by the rkc-setup skill)
- fin-model-evaluation: `(cat:q-fin.ST OR cat:q-fin.CP OR cat:stat.ML OR cat:cs.LG) AND (all:backtest OR all:overfitting OR all:leakage OR all:"cross-validation" OR all:"walk-forward")`
- fin-feature-engineering: `(cat:q-fin.ST OR cat:q-fin.CP OR cat:q-fin.TR OR cat:stat.ML) AND (all:"feature engineering" OR all:"feature selection" OR all:"alternative data")`
- agentic-engineering: `(cat:cs.SE OR cat:cs.AI) AND (all:"coding agent" OR all:"agentic" OR all:"LLM agent")`
- ai-engineering: `(cat:cs.AI OR cat:cs.SE OR cat:cs.MA) AND (all:"agent" AND (all:deployment OR all:production OR all:workflow))`
- motivation-letter-skills: `(cat:cs.CL OR cat:cs.AI) AND (all:"cover letter" OR all:"application letter" OR all:"resume")`
