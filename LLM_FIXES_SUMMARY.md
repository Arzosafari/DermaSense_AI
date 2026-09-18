# LLM Fixes Summary - "Analyze This Image" Failure

## Root Cause Analysis

### Groq 413 Payload Too Large
- **Root Cause**: Multiple large JSON objects with full indentation (`indent=2`) in the LLM prompt
- **Specific Issues**:
  - Disease info, risk assessment, ABCDE analysis, doctor guidance all used `indent=2` 
  - No truncation on risk_assessment, abcde_analysis, doctor_guidance, medical_context_str
  - Only disease_info had truncation logic
  - Template itself is ~117 lines
  - Max prompt limit was 8000 characters, insufficient for all the data

### LM Studio 400 Bad Request  
- **Root Cause**: Model name mismatch and potential request format issues
- **Specific Issues**:
  - Model name `gemma-4-E2B-it-Q4_K_M` might not match exactly what's loaded in LM Studio
  - Request included empty `stop` array which some models don't support
  - Same payload size issues could cause 400 errors
  - Max prompt limit was 10000 characters but insufficient

## Fixes Implemented

### 1. Payload Size Reduction (Image Agent)
**File**: `backend/app/agents/roles/image_agent.py`

**Changes**:
- Removed `indent=2` from all JSON serialization, using `indent=None, separators=(',', ':')` for compact JSON
- Added truncation for all components:
  - Disease info: max 800 chars (down from 1000)
  - Risk assessment: max 500 chars, only essential fields
  - ABCDE analysis: max 300 chars, only score if too large
  - Doctor guidance: max 400 chars, only recommendation if too large
  - Medical context: max 600 chars
  - Symptoms context: max 200 chars
- Reduced overall max prompt length from 8000 to 6000 characters
- Added comprehensive debug logging for prompt composition

### 2. Payload Size Reduction (Conversation Agent)
**File**: `backend/app/agents/roles/conversation_agent.py`

**Changes**:
- Added prompt truncation with max 6000 characters
- Added debug logging for chat history size and composition
- Limited chat history to 2 analysis messages + 3 regular messages

### 3. Groq Adapter Improvements
**File**: `backend/app/llm/adapters/groq_adapter.py`

**Changes**:
- Reduced max prompt length from 8000 to 6000 characters
- Added comprehensive diagnostic logging:
  - Provider, model, messages count
  - Prompt character count, estimated payload size
  - Image/base64 detection
  - Component size estimates
  - Warnings for suspiciously large prompts
- Improved error detection and logging

### 4. LM Studio Adapter Improvements
**File**: `backend/app/llm/adapters/lmstudio_adapter.py`

**Changes**:
- Reduced max prompt length from 10000 to 6000 characters
- Added comprehensive diagnostic logging (same as Groq)
- Fixed request format:
  - Only include `stop` tokens if actually provided (not empty array)
  - Added better error body logging for 400 errors
  - Improved error classification (payload, model, parameter issues)
- Added model name verification logging

### 5. Configuration Updates
**File**: `backend/app/config.py`

**Changes**:
- Added detailed comments about LM_STUDIO_MODEL requirement
- Kept original model name `gemma-4-E2B-it-Q4_K_M` but added documentation
- Added instructions for users to match exact LM Studio model name

### 6. Fallback Logic Improvements
**File**: `backend/app/llm/adapters/fallback_llm.py`

**Changes**:
- Added error classification for Groq (413, auth, rate limit, server errors)
- Added error classification for LM Studio (400, connect, timeout)
- Improved fallback messages based on error type
- Added diagnostic logging for fallback attempts
- Better handling of payload errors (don't just retry, explain the issue)

### 7. Chat Endpoint Error Handling
**File**: `backend/app/api/v1/chat.py`

**Changes**:
- Added detection of LLM errors vs orchestrator success
- Added `llm_error` and `analysis_succeeded` flags in response
- Improved handling of partial success (analysis OK but LLM failed)
- Better user-facing error messages

### 8. Debug Logging Additions
**Files**: Multiple files

**Added comprehensive safe logging**:
- Image agent state diagnostics before prompt construction
- Prompt composition breakdown (each component size)
- Chat history analysis (size, message types)
- LLM request diagnostics (provider, model, size, components)
- Fallback attempt diagnostics
- Error classification and context

**Safety**: Never logs API keys, secrets, or private credentials

## Expected Results

### Before Fixes
- "Analyze this image" → 413 Payload Too Large (Groq) → 400 Bad Request (LM Studio) → Generic error
- Request sizes: ~10,000+ characters with full indentation
- No diagnostic logging to identify issues
- Generic fallback messages

### After Fixes
- "Analyze this image" → Success with ~3,000-5,000 character prompts
- Compact JSON without indentation
- Component-level truncation
- Comprehensive diagnostic logging
- Specific error messages based on failure type
- Partial success handling (analysis succeeds even if LLM fails)

## Testing Recommendations

1. **Test "Analyze this image"** - Should succeed with Groq or fallback to LM Studio
2. **Test "پوستم خارش دارد"** - Persian text analysis should work
3. **Test repeated requests** - No uncontrolled context growth
4. **Test with large profiles** - Should truncate appropriately
5. **Test LM Studio model name** - Verify exact match with loaded model
6. **Test fallback scenarios** - Verify specific error messages

## Configuration Notes

**Important**: Users must ensure `LM_STUDIO_MODEL` in config matches exactly the model name shown in LM Studio's "Loaded Models" section. This can be set via environment variable:

```bash
export LM_STUDIO_MODEL=your_exact_model_name
```

Common model names:
- `gemma-2-9b-it`
- `llama-3-8b-instruct` 
- `mistral-7b-instruct`
- `gemma-4-E2B-it-Q4_K_M`

## Regression Prevention

The fixes maintain all existing functionality:
- ✅ PanDerm pipeline unchanged
- ✅ Classification logic unchanged  
- ✅ Heatmap generation unchanged
- ✅ Medical analysis unchanged
- ✅ Persian language support unchanged
- ✅ User authentication unchanged
- ✅ Memory saving unchanged

Only the LLM communication layer was modified to be more robust and efficient.
