

import asyncio
import chromadb
from chromadb.config import Settings as ChromaSettings
from core.config import get_settings
from core.database import get_supabase_client
from schemas import MemoryCandidate
from services.llm_service import check_root_relevance, check_root_eligibility, check_storage_eligibility
import uuid
from datetime import datetime, timedelta, timezone

settings = get_settings()
# Remove global client
# supabase = get_supabase_client()

# Initialize Chroma
chroma_client = chromadb.PersistentClient(path=settings.CHROMA_DB_PATH)
collection_name = "rooted_ai_memories"
try:
    memory_collection = chroma_client.get_collection(name=collection_name)
except:
    memory_collection = chroma_client.create_collection(name=collection_name)

def classify_priority(candidate: MemoryCandidate) -> str:
    """
    Decide STEM, BRANCH, or LEAF based on context.
    """
    content_lower = candidate.core_content.lower()
    
    # === HARD GUARD: PREVENT BELIEFS/VALUES AS STEM ===
    # Beliefs/Values (Subjective, Present Tense) -> LEAF
    belief_markers = ["i believe", "i think", "i value", "important to me", "should", "opinion"]
    is_belief = any(marker in content_lower for marker in belief_markers)
    
    # Role Identity (Factual) -> STEM allowed
    # (e.g. "i am a", "my job is", "i live in") - simplistic check, but effective for now
    role_markers = ["i am a", "i work as", "i live in", "my role is"]
    is_role = any(marker in content_lower for marker in role_markers)
    
    if is_belief and not is_role:
        return "LEAF"

    # === STANDARD CLASSIFICATION ===
    if candidate.category == "identity" or candidate.time_scale == "long_term":
        return "STEM"
    
    if candidate.category == "habit" or candidate.time_scale == "repeated":
        return "BRANCH"
        
    if candidate.confidence > 0.9 and candidate.importance == "high":
        return "STEM"

    return "LEAF"

def decay_memories(user_id: str, supabase_client):
    """
    Lifecycle management:
    - LEAF: Expires after 48 hours.
    - BRANCH: Demoted to LEAF if unused for 7 days.
    """
    now = datetime.now(timezone.utc)
    
    # 1. Delete old LEAF nodes
    expiry_time = now - timedelta(hours=48)
    
    # We first find IDs to delete from Chroma
    to_delete = supabase_client.table("memory_nodes")\
        .select("id")\
        .eq("user_id", user_id)\
        .eq("priority", "LEAF")\
        .lt("created_at", expiry_time.isoformat())\
        .execute()
        
    delete_ids = [row['id'] for row in to_delete.data]
    
    if delete_ids:
        # Delete from Supabase
        supabase_client.table("memory_nodes").delete().in_("id", delete_ids).execute()
        # Delete from Chroma
        try:
            memory_collection.delete(ids=delete_ids)
        except Exception as e:
            print(f"Chroma delete error: {e}")

    # 2. Demote stale BRANCH nodes
    stale_time = now - timedelta(days=7)
    
    # Find branches not updated recently
    stale_branches = supabase_client.table("memory_nodes")\
        .select("id")\
        .eq("user_id", user_id)\
        .eq("priority", "BRANCH")\
        .lt("last_used_at", stale_time.isoformat())\
        .execute()
        
    branch_ids = [row['id'] for row in stale_branches.data]
    
    if branch_ids:
        supabase_client.table("memory_nodes")\
            .update({"priority": "LEAF"})\
            .in_("id", branch_ids)\
            .execute()

        # Update metadata in Chroma
        pass

def process_memory_candidates(user_id: str, candidates: list[MemoryCandidate], supabase_client) -> dict:
    results = {
        "processed": 0,
        "root_updates": 0,
        "new_memories": 0,
        "reinforced": 0,
        "discarded": 0
    }
    
    # Pre-fetch Root Profile ONCE for the batch to minimize reads
    root_res = supabase_client.table("root_profile").select("*").eq("user_id", user_id).maybe_single().execute()
    root_profile = root_res.data if root_res and root_res.data else None
    
    for candidate in candidates:
        results["processed"] += 1
        
        # === GATE 1: ROOT ELIGIBILITY (The Persona Anchor) ===
        eligibility = check_root_eligibility(candidate)
        
        if eligibility.get("is_eligible"):
            print(f"ROOT UPDATE DETECTED: {eligibility}")
            
            # Prepare updates
            new_summary = eligibility.get("summary_update", "")
            new_traits = eligibility.get("extracted_traits", {})
            new_values = eligibility.get("extracted_values", [])
            
            # Merge with existing profile if it exists
            if root_profile:
                # Merge traits
                existing_traits = root_profile.get("traits") or {}
                existing_traits.update(new_traits)
                
                # Merge values (unique list)
                existing_values = root_profile.get("values") or []
                merged_values = list(set(existing_values + new_values))
                
                # Update summary
                current_summary = root_profile.get("persona_summary", "")
                if new_summary and new_summary not in current_summary:
                    updated_summary = f"{current_summary}. {new_summary}".strip()
                else:
                    updated_summary = current_summary

                updates = {
                    "persona_summary": updated_summary,
                    "traits": existing_traits,
                    "values": merged_values,
                    "last_updated_at": datetime.now(timezone.utc).isoformat()
                }
                
                supabase_client.table("root_profile").update(updates).eq("user_id", user_id).execute()
                
                # Update local root_profile variable in case next candidate needs it
                root_profile.update(updates)
                
            else:
                # Create NEW Root Profile
                new_profile = {
                    "user_id": user_id,
                    "persona_summary": new_summary,
                    "traits": new_traits,
                    "values": new_values,
                    "confidence_score": 1.0,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "last_updated_at": datetime.now(timezone.utc).isoformat()
                }
                supabase_client.table("root_profile").insert(new_profile).execute()
                root_profile = new_profile

            results["root_updates"] += 1
            continue # STOP processing this candidate (absorbed into ROOT)

        # === GATE 2: STORAGE WORTHINESS (Noise Filter) ===
        if not check_storage_eligibility(candidate):
            results["discarded"] += 1
            continue

        # === STANDARD MEMORY STORAGE ===
        
        # Check Alignment with Root
        alignment = check_root_relevance(candidate.core_content, root_profile)
        
        # Priority Classification
        priority = classify_priority(candidate)        
        
        # If priority == LEAF AND domain == "general" AND importance is low -> DISCARD
        # (Double check, although Gate 2 handles most)
        if priority == "LEAF" and candidate.importance == "low" and candidate.category == "event":
            results["discarded"] += 1
            continue

        # Alignment Enforcement
        if alignment == "contradictory":
            priority = "LEAF" # Demote contradictory facts

        # Duplicate Check / Reinforcement
        match = memory_collection.query(
            query_texts=[candidate.core_content],
            n_results=1,
            where={"user_id": user_id}
        )

        existing_id = None
        existing_distance = 100
        
        if match["ids"] and match["ids"][0]:
            existing_id = match["ids"][0][0]
            existing_distance = match["distances"][0][0]

        # Reinforce if very similar
        if existing_id and existing_distance < 0.25: # Strict similarity
            record = supabase_client.table("memory_nodes").select("*").eq("id", existing_id).single().execute()
            data = record.data
            
            new_count = (data.get('reinforcement_count') or 1) + 1
            new_confidence = min(1.0, data.get('confidence', 0.5) + 0.1)
            
            updates = {
                "reinforcement_count": new_count,
                "confidence": new_confidence,
                "last_used_at": datetime.now(timezone.utc).isoformat(),
                "root_alignment": alignment
            }
            
            # Promotion Logic
            if data['priority'] == "LEAF" and new_count >= 3 and alignment != "contradictory":
                updates['priority'] = "BRANCH"
            
            # STEM Promotion (Very Strict)
            if data['priority'] == "BRANCH" and new_confidence > 0.95 and candidate.time_scale == "long_term":
                 updates['priority'] = "STEM"
                
            supabase_client.table("memory_nodes").update(updates).eq("id", existing_id).execute()
            results["reinforced"] += 1
            
        else:
            # Insert NEW
            row = {
                "user_id": user_id,
                "domain": candidate.domain,
                "priority": priority,
                "node_type": candidate.category,
                "content": candidate.core_content,
                "confidence": candidate.confidence,
                "reinforcement_count": 1,
                "last_used_at": datetime.now(timezone.utc).isoformat(),
                "root_alignment": alignment
            }
            
            res = supabase_client.table("memory_nodes").insert(row).execute()
            record_id = res.data[0]['id']
            
            metadata = {
                "user_id": user_id,
                "domain": candidate.domain,
                "priority": priority,
                "type": candidate.category,
                "root_alignment": alignment
            }
            
            memory_collection.add(
                documents=[candidate.core_content],
                metadatas=[metadata],
                ids=[record_id]
            )
            results["new_memories"] += 1

    return results

async def retrieve_relevant_memory(user_id: str, query: str, domains: list[str], supabase_client) -> dict:
    """
    Tree-Guided Retrieval (Optimized):
    Executes independent fetches in parallel:
    0. ROOT: The core persona anchor.
    1. STEM: ALL stem nodes (Identity/Facts) - Unconditional
    2. BRANCH: Active branches matching domain
    3. LEAF: Only recent & relevant (Vector Search)
    """
    
    # Define helper functions for each independent task to run in threads
    def fetch_root():
        res = supabase_client.table("root_profile").select("*").eq("user_id", user_id).maybe_single().execute()
        return res.data if res and res.data else {}

    def fetch_stem():
        res = supabase_client.table("memory_nodes")\
            .select("content")\
            .eq("user_id", user_id)\
            .eq("priority", "STEM")\
            .execute()
        return [row['content'] for row in res.data]

    def fetch_branch():
        if not domains:
            return []
        res = supabase_client.table("memory_nodes")\
            .select("content")\
            .eq("user_id", user_id)\
            .eq("priority", "BRANCH")\
            .in_("domain", domains)\
            .execute()
        return [row['content'] for row in res.data]

    def fetch_leaf():
        where_clause = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"priority": {"$eq": "LEAF"}}
            ]
        }
        results = memory_collection.query(
            query_texts=[query],
            n_results=5,
            where=where_clause
        )
        if results["documents"]:
            return results["documents"][0]
        return []

    # Execute all tasks in parallel using asyncio.gather and to_thread
    root_data, stem_data, branch_data, leaf_data = await asyncio.gather(
        asyncio.to_thread(fetch_root),
        asyncio.to_thread(fetch_stem),
        asyncio.to_thread(fetch_branch),
        asyncio.to_thread(fetch_leaf)
    )

    return {
        "root": root_data,
        "stem": stem_data,
        "branch": branch_data,
        "leaf": leaf_data
    }
