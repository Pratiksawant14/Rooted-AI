
import chromadb
from chromadb.config import Settings as ChromaSettings
from core.config import get_settings
from core.database import get_supabase_client
from schemas import AnalyzedContext
from services.llm_service import check_root_relevance, check_root_eligibility
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

def classify_priority(context: AnalyzedContext) -> str:
    """
    Decide STEM, BRANCH, or LEAF based on context.
    """
    if context.category == "identity" or context.time_scale == "long_term":
        return "STEM"
    
    if context.category == "habit" or context.time_scale == "repeated":
        return "BRANCH"
        
    if context.confidence > 0.9 and context.importance == "high":
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

def store_memory(user_id: str, context: AnalyzedContext, supabase_client) -> dict:
    # 0. Fetch ROOT Profile
    root_res = supabase_client.table("root_profile").select("*").eq("user_id", user_id).maybe_single().execute()
    root_profile = root_res.data if root_res and root_res.data else None
    
    # === NEW: ROOT ELIGIBILITY CHECK (HARD GATE) ===
    # Check if this memory belongs in the Persona Anchor Layer
    eligibility = check_root_eligibility(context)
    
    if eligibility.get("is_eligible"):
        print(f"ROOT UPDATE DETECTED: {eligibility}")

        # RATE LIMITING: Prevent Persona Drift
        # Rule: Only 1 ROOT update every 10 minutes (unless new profile)
        if root_profile:
            last_update = datetime.fromisoformat(root_profile.get("last_updated_at", str(datetime.min)))
            time_since = datetime.now(timezone.utc) - last_update
            if time_since < timedelta(minutes=10):
                print(f"ROOT UPDATE SKIPPED: Rate limit active ({time_since} < 10m)")
                return {"status": "skipped_rate_limit", "reason": "Persona drift protection"}
        
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
            
            # Update summary (append logic or replace - for now we append if new)
            current_summary = root_profile.get("persona_summary", "")
            if new_summary and new_summary not in current_summary:
                updated_summary = f"{current_summary}. {new_summary}".strip()
            else:
                updated_summary = current_summary

            supabase_client.table("root_profile").update({
                "persona_summary": updated_summary,
                "traits": existing_traits,
                "values": merged_values,
                "last_updated_at": datetime.now(timezone.utc).isoformat()
            }).eq("user_id", user_id).execute()
            
        else:
            # Create NEW Root Profile
            supabase_client.table("root_profile").insert({
                "user_id": user_id,
                "persona_summary": new_summary,
                "traits": new_traits,
                "values": new_values,
                "confidence_score": 1.0,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "last_updated_at": datetime.now(timezone.utc).isoformat()
            }).execute()
            
        # HARD STOP: Do not store as memory node
        return {"status": "root_updated", "details": eligibility}

    # === STANDARD PIPELINE FOLLOWS ===

    # Check Alignment
    alignment = check_root_relevance(context.core_content, root_profile)

    # 1. Noise Filtering
    # If priority == LEAF AND domain == "general" AND importance is low -> DISCARD
    priority = classify_priority(context)
    primary_domain = context.domains[0] if context.domains else "general"

    if priority == "LEAF" and "general" in context.domains and context.importance == "low":
        return None

    # ROOT MODIFIER RULE:
    # If candidate contradicts ROOT -> prevent promotion, keep as LEAF
    if alignment == "contradictory":
        priority = "LEAF"

    # 2. Check for Duplicates / Reinforcement
    # Search Chroma for very similar content
    results = memory_collection.query(
        query_texts=[context.core_content],
        n_results=1,
        where={"user_id": user_id}
    )

    existing_id = None
    existing_distance = 100
    
    if results["ids"] and results["ids"][0]:
        existing_id = results["ids"][0][0]
        existing_distance = results["distances"][0][0]

    # Threshold for "Same Memory". Chroma distance: lower is closer. 
    # Let's assume < 0.3 implies very close semantic match.
    if existing_id and existing_distance < 0.3:
        # REINFORCE
        # Fetch current record
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
        
        # PROMOTION LOGIC
        # LEAF -> BRANCH if count >= 3 AND not contradictory
        if data['priority'] == "LEAF" and new_count >= 3 and alignment != "contradictory":
            updates['priority'] = "BRANCH"
        
        # BRANCH -> STEM if long-term + high confidence (strict) AND aligned/neutral
        if data['priority'] == "BRANCH" and new_confidence > 0.9 and context.time_scale == "long_term" and alignment != "contradictory":
            updates['priority'] = "STEM"
            
        final = supabase_client.table("memory_nodes").update(updates).eq("id", existing_id).execute()
        return final.data[0]
        
    else:
        # INSERT NEW
        row = {
            "user_id": user_id,
            "domain": primary_domain,
            "priority": priority,
            "node_type": context.category, # category
            "content": context.core_content,
            "confidence": context.confidence,
            "reinforcement_count": 1,
            "last_used_at": datetime.now(timezone.utc).isoformat(),
            "root_alignment": alignment
        }
        
        data = supabase_client.table("memory_nodes").insert(row).execute()
        record = data.data[0]
        record_id = record['id']
        
        metadata = {
            "user_id": user_id,
            "domain": primary_domain,
            "priority": priority,
            "type": context.category,
            "root_alignment": alignment
        }
        
        memory_collection.add(
            documents=[context.core_content],
            metadatas=[metadata],
            ids=[record_id]
        )
        
        return record

def retrieve_relevant_memory(user_id: str, query: str, domains: list[str], supabase_client) -> dict:
    """
    Tree-Guided Retrieval:
    0. ROOT: The core persona anchor.
    1. STEM: ALL stem nodes (Identity/Facts) - Unconditional
    2. BRANCH: Active branches matching domain
    3. LEAF: Only recent & relevant (Vector Search)
    """
    
    memory_map = {
        "root": {},
        "stem": [],
        "branch": [],
        "leaf": []
    }

    # 0. FETCH ROOT
    root_res = supabase_client.table("root_profile").select("*").eq("user_id", user_id).maybe_single().execute()
    if root_res and root_res.data:
        memory_map["root"] = root_res.data
    
    # 1. FETCH STEM (All, or heavily prioritized)
    stems = supabase_client.table("memory_nodes")\
        .select("content")\
        .eq("user_id", user_id)\
        .eq("priority", "STEM")\
        .execute()
        
    memory_map["stem"] = [row['content'] for row in stems.data]
    
    # 2. FETCH BRANCH (Filter by domain if present, else relevant ones)
    if domains:
        branches = supabase_client.table("memory_nodes")\
            .select("content")\
            .eq("user_id", user_id)\
            .eq("priority", "BRANCH")\
            .in_("domain", domains)\
            .execute()
        memory_map["branch"] = [row['content'] for row in branches.data]
        
    # 3. FETCH LEAF (Vector Search)
    # We query Chroma strictly for leaves or just query broadly and filter
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
        memory_map["leaf"] = results["documents"][0]
        
    return memory_map
