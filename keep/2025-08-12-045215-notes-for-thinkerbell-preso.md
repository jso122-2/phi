# notes for thinkerbell preso

#keep #imported

> created_ts: 2025-08-12-045215  
> Created: 2025-08-12 04:52 UTC  
> Edited: 2025-08-12 11:15 UTC  
> Source: Google Keep  

---

Dataset Discovery → EDA Validation → Data Splitting → K-Kernel Mining → 
Training → Embeddings Export → Evaluation → FAISS Build → Service Reload

"We trained a contract-type classifier + semantic retriever on 5,000 domain-specific synthetic samples, reaching 64% Recall@5 in under 25 minutes of CPU-only training. The architecture is modular — tomorrow we can scale this same pipeline on GPU with richer data to reach production-grade accuracy." 

“What you’re seeing is a local, production-shaped prototype. We trained a lightweight encoder on 5k style-conditioned samples, built a FAISS HNSW index, and serve it behind a tiny FastAPI. Search is sub-100ms per query on CPU, and the pipeline is GPU-ready for our next pass. Today’s goal is proof of fit; tomorrow we switch to Linux/WSL for CUDA + FAISS-GPU and push the metrics.” 

checklist

8-11 

train models 
clean ubuntu  -
set up docker 

11-3

set up redis 
set up minio

3-5 

javascript errors and polish 

SLEEP

---

## Semantic links

→ [[live-state]]
→ [[psspps]]

## Related notes

→ [[keep/2025-08-12-113813-2025-08-12t21-46-58-844-10-00]]
→ [[keep/2025-08-12-143918-2025-08-13t00-39-18-454-10-00]]
→ [[keep/2025-08-29-085046-2025-08-29t18-50-47-129-10-00]]
→ [[keep/2025-08-12-114713-2025-08-12t22-43-58-059-10-00]]
→ [[keep/2025-05-21-014854-sever-build-list-21-5-25]]

→ [[keep]] — import index  

*Imported by `graph/ingestion.py` — links via MiniLM all-MiniLM-L6-v2*

---

## Auto-linked

→ [[keep-index]]
→ [[2025-06-08-062357-fresh-termial-instate-gpt]]
→ [[2025-12-12-032609-formulas-1212-25]]
→ [[2025-08-12-011708-a-disiplined-rebillion]]
→ [[2025-05-19-163744-server-scribble]]
→ [[2025-12-10-120936-2025-12-10t23-39-19-648-11-00]]

→ [[2025-12-13-051108-formulas-13-12-25]]
→ [[2025-12-13-062815-miler-coat-of-arms]]
→ [[2025-09-19-041208-neofetch]]
→ [[2025-05-28-154122-dawn-test-1]]
→ [[2025-08-09-044150-soot-ash-residue-dynamics-in-dawn]]
→ [[2025-05-15-081254-2025-05-15t18-22-57-859-10-00]]

→ [[2025-08-18-101454-security]]
→ [[2025-05-28-224414-2025-05-29t08-44-14-473-10-00]]
→ [[2025-02-20-075321-docker-and-celery-commands]]
→ [[2025-04-10-125121-tanatlus-prompt]]
→ [[2025-10-06-150602-2025-10-07t02-07-04-211-11-00]]
→ [[2025-03-03-074553-gti-commands]]

→ [[2025-02-13-044420-conda-churn-final-env-packages]]
→ [[2025-05-27-104057-visual-suite]]
→ [[2025-12-06-123319-rag-formula]]
→ [[2025-05-15-113345-pretty-code]]
→ [[2025-08-13-102831-2025-08-13t20-40-07-038-10-00]]
→ [[2025-09-09-072136-2025-09-09t17-21-36-865-10-00]]

→ [[environment]]
→ [[2025-06-08-063438-linux-first-checklist-8-6-25]]
→ [[2025-07-14-082119-2025-07-14t18-21-19-769-10-00]]
→ [[2025-05-28-145651-2025-05-29t00-56-55-879-10-00]]
→ [[2025-05-26-141917-dawn-tests]]
→ [[2026-04-30-131517-dawn-super-rich-kids]]
