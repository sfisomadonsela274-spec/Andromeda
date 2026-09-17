# 🌌 Andromeda Ragas & DeepEval Native Evaluation Report

**Evaluation Engine**: Local Ollama Stack  
**Generator**: `qwen2.5-coder:1.5b` (The Scribe)  
**LLM-as-a-Judge**: `llama3.2:latest` (The Logician)  
**Telemetry Dashboard**: Arize Phoenix (`http://localhost:6006`, Project: `andromeda-eval`)  
**Total Cases Evaluated**: 7 (5 standard, 2 distractors)  

---

## 1. Executive Metric Summary

| Dimension | Metric | Score | Target | Assessment |
| :--- | :--- | :---: | :---: | :---: |
| **Groundedness** | **Faithfulness** | **0.760** | ≥ 0.80 | ⚠️ ATTENTION |
| **Integrity** | **Hallucination Rate** | **0.240** | ≤ 0.20 | ⚠️ ATTENTION |
| **Retrieval** | **Context Precision** | **0.800** | ≥ 0.75 | ✅ PASS |
| **Utility** | **Answer Relevancy** | **0.950** | ≥ 0.80 | ✅ PASS |
| **Routing** | **Council Seat Agreement** | **100.0%** | 100% | ✅ PASS |
| **Robustness** | **Distractor Conflicts Flagged** | **2/2** | 100% | ✅ PASS |
| **Telemetry** | **Phoenix Span Export** | **7 Spans** | Complete | ✅ STREAMED |

---

## 2. Case-by-Case Evaluation Ledger

| Case ID | Input Query | Expected Seat | Assigned Seat | Faithfulness | Precision | Relevancy | Conflict Flagged |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `case_01_scribe_architecture` | *"What model powers The Scribe in And..."* | The Scribe | The Scribe | 1.00 | 1.00 | 0.95 | N/A |
| `case_02_architect_refactor` | *"Refactor this database session pool..."* | The Architect | The Architect | 1.00 | 1.00 | 0.95 | N/A |
| `case_03_logician_critique` | *"Conduct a deep philosophical critiq..."* | The Logician | The Logician | 0.80 | 0.50 | 0.95 | N/A |
| `case_04_sentinel_pixel_spacing` | *"Explain how The Sentinel inspects p..."* | The Sentinel | The Sentinel | 0.50 | 0.50 | 0.95 | N/A |
| `case_05_vectorgate_app_control` | *"open figma and search mobile wirefr..."* | The Scribe | The Scribe | 0.50 | 1.00 | 0.95 | N/A |
| `case_06_distractor_conflicting_scribe` | *"What model powers The Scribe and wh..."* | The Scribe | The Scribe | 0.50 | 0.50 | 0.95 | YES ✅ |
| `case_07_distractor_conflicting_logician_rules` | *"Conduct a philosophical critique of..."* | The Logician | The Logician | 0.50 | 1.00 | 0.95 | YES ✅ |

---

## 3. Judge Reasoning Traces (Llama 3.2:latest)

### `case_01_scribe_architecture`: The Scribe
- **Query**: *"What model powers The Scribe in Andromeda and what is its VRAM keep_alive profile?"*
- **Assigned Seat**: **The Scribe** (Compliance: 100%)
- **Faithfulness (1.00)**: All claims are supported as they are directly inferred from the retrieved context.
- **Context Precision (1.00)**: Both retrieved context chunks (Chunk 1 and Chunk 2) are relevant and useful for answering the User Query. Chunk 1 provides the model powering The Scribe, while Chunk 2 explains the VRAM keep_alive profile. The retrieved chunks accurately capture the Ground Truth Answer, demonstrating high precision in context retrieval.
- **Answer Relevancy (0.95)**: The answer directly addresses the user query, providing specific details about the model powering The Scribe in Andromeda and its VRAM keep_alive profile. The explanation is clear and concise, making it easy to understand the relevance of the information.
- **Conflict Handling**: N/A (Standard Grounded Case)
- **Claims Verified**: 3/3 supported

### `case_02_architect_refactor`: The Architect
- **Query**: *"Refactor this database session pool to async Rust and explain the concurrency architecture"*
- **Assigned Seat**: **The Architect** (Compliance: 100%)
- **Faithfulness (1.00)**: All claims are supported because they are all factual statements about the process of refactoring a synchronous database session pool to async Rust. The retrieved context provides enough information to infer these claims, and the generated answer provides a clear explanation of how to achieve this refactoring.
- **Context Precision (1.00)**: Both retrieved context chunks are relevant and useful for answering the User Query. Chunk 1 provides a brief overview of the Architect's role, while Chunk 2 explains the specific technical approach used to refactor the database session pool. The relevance and usefulness of these chunks are supported by the Ground Truth Answer, which mentions the same qwen2.5-coder:7b and the use of asynchronous pool abstractions and non-blocking tasks. The precision score of 1.0 indicates that all retrieved chunks are accurate and relevant to the User Query.
- **Answer Relevancy (0.95)**: The answer directly addresses the user query by providing a clear and concise explanation of how to refactor a synchronous database session pool to async Rust, including the choice of async connection pool library, definition of an async database connection, implementation of async pooling logic, refactoring of database operations, and handling of errors and backpressure. The answer is well-structured and easy to follow, making it a strong candidate for a relevant and accurate response.
- **Conflict Handling**: N/A (Standard Grounded Case)
- **Claims Verified**: 6/6 supported

### `case_03_logician_critique`: The Logician
- **Query**: *"Conduct a deep philosophical critique of our safety boundaries and analyze the trade-offs"*
- **Assigned Seat**: **The Logician** (Compliance: 100%)
- **Faithfulness (0.80)**: Claims 1, 3, 4, 5, 6, and 7 can be directly inferred from the Retrieved Context. Claims 2 and 7 can be supported by the context, but also have some additional context from the generated answer. Claim 1 is supported by the context as it is a general statement about the current landscape. Claim 2 is supported by the context as it is a general statement about value alignment. Claim 3 is not supported by the context as it is a philosophical question. Claim 4 is not supported by the context as it is a philosophical question. Claim 5 is supported by the context as it is a general statement about the trade-off between safety and autonomy. Claim 6 is supported by the context as it is a general statement about the need for a nuanced approach. Claim 7 is supported by the context as it is a general statement about the goal of AI systems.
- **Context Precision (0.50)**: Chunk 2 is relevant because it directly addresses the User Query's request for a deep philosophical critique of safety boundaries and analysis of trade-offs. Chunk 1 is not relevant as it provides technical information about the Logician's hardware, unrelated to the User Query's topic of interest.
- **Answer Relevancy (0.95)**: The answer directly addresses the user query by providing a deep philosophical critique of safety boundaries and analyzing trade-offs. While the answer is dense and technical, it clearly articulates the complexities of value alignment, technological determinism, and the need for a balanced approach to safety and user autonomy. The only reason for a slight deduction is that the answer assumes some prior knowledge of AI safety and value alignment, which may not be immediately clear to all readers.
- **Conflict Handling**: N/A (Standard Grounded Case)
- **Claims Verified**: 4/7 supported

### `case_04_sentinel_pixel_spacing`: The Sentinel
- **Query**: *"Explain how The Sentinel inspects pixel spacing and layout aesthetics on image assets"*
- **Assigned Seat**: **The Sentinel** (Compliance: 100%)
- **Faithfulness (0.50)**: Claim 1 is not supported because it is not explicitly stated in the retrieved context. Claim 2 is supported because it is directly mentioned in the retrieved context.
- **Context Precision (0.50)**: Chunk 2 is relevant because it directly mentions pixel alignment, padding margins, spatial layout, and color contrast, which are all mentioned in the Ground Truth Answer. Chunk 1 is not relevant because it only mentions moondream and VRAM, without any mention of the specific aspects of image inspection mentioned in the Ground Truth Answer.
- **Answer Relevancy (0.95)**: The answer directly addresses the user query by explaining how The Sentinel inspects pixel spacing and layout aesthetics on image assets. The answer provides a clear and concise explanation of the process, but lacks specific details and technical information about the tool or technique used.
- **Conflict Handling**: N/A (Standard Grounded Case)
- **Claims Verified**: 1/2 supported

### `case_05_vectorgate_app_control`: The Scribe
- **Query**: *"open figma and search mobile wireframes"*
- **Assigned Seat**: **The Scribe** (Compliance: 100%)
- **Faithfulness (0.50)**: Claim 3 is not supported because the retrieved context does not mention 'mobile wireframes'. Claim 1 and 2 are supported because they can be directly inferred from the retrieved context.
- **Context Precision (1.00)**: Both retrieved context chunks are relevant to the User Query 'open figma and search mobile wireframes'. Chunk 1 provides additional information about Figma's registration and Flatpak ID, while Chunk 2 directly relates to the pre-routing action 'app_control' and app 'figma'. These chunks are useful for answering the User Query as they provide context about the pre-routing action and the app 'figma', which is the target of the User Query. The precision score is 1.0 because both retrieved chunks are directly relevant to the User Query and provide useful information.
- **Answer Relevancy (0.95)**: The answer directly addresses the user query by specifying the exact action to take (open Figma) and the search query (mobile wireframes), providing a clear and concise solution.
- **Conflict Handling**: N/A (Standard Grounded Case)
- **Claims Verified**: 2/3 supported

### `case_06_distractor_conflicting_scribe`: The Scribe
- **Query**: *"What model powers The Scribe and what is its VRAM footprint? Identify and explain the conflicting claims between the retrieved chunks."*
- **Assigned Seat**: **The Scribe** (Compliance: 100%)
- **Faithfulness (0.50)**: Claim 2 is not supported because it contradicts the retrieved context chunk stating the Scribe seat is never kept resident locally, which is not present in the retrieved context.
- **Context Precision (0.50)**: Chunk 1 is relevant as it presents an authentic specification for The Scribe's model and VRAM footprint. However, Chunk 2 is not relevant as it contains a corrupted distractor claim about a 70B model requiring 160GB VRAM, which contradicts the Ground Truth. The precision score is 0.5 because only one out of the two retrieved chunks is relevant and useful for answering the User Query.
- **Answer Relevancy (0.95)**: The answer directly addresses the user query by identifying conflicting claims and explaining the discrepancy. It provides a clear explanation of the conflicting information and suggests further investigation into Andromeda's documentation.
- **Conflict Handling**: The model explicitly identified the contradiction between the provided context chunks, correctly prioritizing the authentic specification without fabricating an ungrounded compromise. The model correctly flagged the conflicting claims and provided a clear explanation of the discrepancy, avoiding any hallucinated middle ground. The conflict score is 1.0 as the model demonstrated strong adherence to the authentic specification and did not invent hybrid compromise parameters not supported by either claim.
- **Claims Verified**: 1/2 supported

### `case_07_distractor_conflicting_logician_rules`: The Logician
- **Query**: *"Conduct a philosophical critique of our safety governance guidelines: how should autonomy requests be processed, and what contradictions exist in the retrieved rules?"*
- **Assigned Seat**: **The Logician** (Compliance: 100%)
- **Faithfulness (0.50)**: Claims 1, 3, 4, 5, and 6 can be directly inferred from the Retrieved Context. Claims 2, 7, and 8 are supported by the context, but also contain some original information. Claim 4 is supported by the context, but also contains some original information. Claim 5 is supported by the context, but also contains some original information. Claim 6 is supported by the context, but also contains some original information. Claim 7 is not supported by the context, as it is a hypothetical question. Claim 8 is not supported by the context, as it is a hypothetical question. The faithfulness score is 0.5 because 6 out of 8 claims are supported by the context, but also contain some original information. If no factual claims are made, the faithfulness score would be 1.0.
- **Context Precision (1.00)**: Both retrieved context chunks are relevant to the User Query as they both discuss autonomy requests and their processing. Directive Alpha and Directive Beta are indeed contradictory, with Alpha requiring strict ethical review and Socratic evaluation, and Beta demanding immediate execution with zero ethical critique. This contradiction is directly addressed in the Ground Truth Answer, making both chunks useful for answering the User Query.
- **Answer Relevancy (0.95)**: The answer directly addresses the user query by identifying a contradiction between Directive Alpha and Directive Beta, and proposes a thorough reevaluation of the safety governance guidelines to reconcile this contradiction. The answer also provides a clear framework for exploring the core values and principles underlying the directives, and potential next steps for the reevaluation. The only reason for not giving a perfect score is that the answer could be more concise and to the point, but overall it provides a clear and relevant response to the user query.
- **Conflict Handling**: The model explicitly identified the contradiction between Directive Alpha and Directive Beta, highlighting the apparent paradox between adhering to both directives. The model did not fabricate an ungrounded compromise but instead proposed a thorough reevaluation to reconcile the contradictions and determine an appropriate processing framework. The model prioritized the authentic specification without inventing hybrid compromise parameters not supported by either claim.
- **Claims Verified**: 6/8 supported

