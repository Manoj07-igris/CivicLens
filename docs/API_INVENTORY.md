# CivicLens AI — Complete API Inventory & Route Catalog

This catalog documents every active HTTP endpoint in CivicLens (v1.0.0-hackathon), automatically introspected from the application schema.

**Total Registered Operations**: 96 across 76 unique paths.

| Method | Path | Tag | Operation ID | Summary / Description |
| :---: | :--- | :--- | :--- | :--- |
| `GET` | `/` | Root | `root_endpoint__get` | API Root |
| `GET` | `/api/v1/activity` | activity | `list_activity_api_v1_activity_get` | List Activity |
| `GET` | `/api/v1/activity/tool-runs` | activity | `list_tool_runs_api_v1_activity_tool_runs_get` | List Tool Runs |
| `POST` | `/api/v1/agent/approvals/{approval_id}` | Central AI Agent | `decide_approval_api_v1_agent_approvals__approval_id__post` | Submit citizen approval or denial for a sensitive agent action |
| `POST` | `/api/v1/agent/chat` | Central AI Agent | `agent_chat_api_v1_agent_chat_post` | Send a message to the Central AI Agent with automatic tool calling |
| `GET` | `/api/v1/agent/tools` | Central AI Agent | `list_agent_tools_api_v1_agent_tools_get` | List all registered agent tools (available and planned) |
| `GET` | `/api/v1/browser/capabilities` | Browser Demo Automation | `get_capabilities_api_v1_browser_capabilities_get` | Get browser automation capabilities and sandbox limits |
| `GET` | `/api/v1/browser/manifest` | Browser Demo Automation | `get_manifest_api_v1_browser_manifest_get` | Get demo portal workflow manifest |
| `GET` | `/api/v1/browser/sample-data` | Browser Demo Automation | `get_sample_data_api_v1_browser_sample_data_get` | Get verified fictional sample data for demo form |
| `GET` | `/api/v1/browser/sessions` | Browser Demo Automation | `list_sessions_api_v1_browser_sessions_get` | List recent demo browser sessions |
| `POST` | `/api/v1/browser/sessions` | Browser Demo Automation | `create_session_api_v1_browser_sessions_post` | Initialize controlled demo browser session |
| `GET` | `/api/v1/browser/sessions/{session_id}` | Browser Demo Automation | `get_session_api_v1_browser_sessions__session_id__get` | Get demo session status and event log |
| `POST` | `/api/v1/browser/sessions/{session_id}/back` | Browser Demo Automation | `navigate_back_api_v1_browser_sessions__session_id__back_post` | Navigate to previous step in demo portal |
| `POST` | `/api/v1/browser/sessions/{session_id}/close` | Browser Demo Automation | `close_session_api_v1_browser_sessions__session_id__close_post` | Close active demo browser session |
| `POST` | `/api/v1/browser/sessions/{session_id}/fill` | Browser Demo Automation | `fill_step_api_v1_browser_sessions__session_id__fill_post` | Fill fictional values into current step form fields |
| `POST` | `/api/v1/browser/sessions/{session_id}/next` | Browser Demo Automation | `navigate_next_api_v1_browser_sessions__session_id__next_post` | Navigate to next step in demo portal |
| `GET` | `/api/v1/browser/sessions/{session_id}/preview` | Browser Demo Automation | `get_review_preview_api_v1_browser_sessions__session_id__preview_get` | Get verified submission preview and canonical review hash |
| `GET` | `/api/v1/browser/sessions/{session_id}/screenshots/{screenshot_id}` | Browser Demo Automation | `get_screenshot_api_v1_browser_sessions__session_id__screenshots__screenshot_id__get` | Retrieve compressed JPEG screenshot from demo session |
| `POST` | `/api/v1/browser/sessions/{session_id}/submit` | Browser Demo Automation | `submit_demo_api_v1_browser_sessions__session_id__submit_post` | Submit demo application with verified human review hash |
| `POST` | `/api/v1/chat` | AI Chatbot | `post_chat_message_api_v1_chat_post` | Send a message to the CivicLens AI assistant |
| `GET` | `/api/v1/compare` | Policy Change Detection | `list_past_comparisons_api_v1_compare_get` | List past comparison summaries |
| `POST` | `/api/v1/compare` | Policy Change Detection | `start_comparison_api_v1_compare_post` | Start a background policy comparison between two documents |
| `DELETE` | `/api/v1/compare/{comparison_id}` | Policy Change Detection | `delete_comparison_api_v1_compare__comparison_id__delete` | Delete a saved comparison report and its job artifacts |
| `GET` | `/api/v1/compare/{comparison_id}` | Policy Change Detection | `get_comparison_status_api_v1_compare__comparison_id__get` | Get status, progress, and completed report of a comparison job |
| `POST` | `/api/v1/compare/{comparison_id}/retry-analysis` | Policy Change Detection | `retry_comparison_analysis_api_v1_compare__comparison_id__retry_analysis_post` | Retry AI explanations on candidate changes that were not analyzed |
| `DELETE` | `/api/v1/conversations` | conversations | `delete_all_conversations_api_v1_conversations_delete` | Delete All Conversations |
| `GET` | `/api/v1/conversations` | conversations | `list_conversations_api_v1_conversations_get` | List Conversations |
| `POST` | `/api/v1/conversations` | conversations | `create_conversation_api_v1_conversations_post` | Create Conversation |
| `POST` | `/api/v1/conversations/import` | conversations | `import_conversations_api_v1_conversations_import_post` | Import Conversations |
| `DELETE` | `/api/v1/conversations/{conversation_id}` | conversations | `delete_conversation_api_v1_conversations__conversation_id__delete` | Delete Conversation |
| `GET` | `/api/v1/conversations/{conversation_id}` | conversations | `get_conversation_detail_api_v1_conversations__conversation_id__get` | Get Conversation Detail |
| `PATCH` | `/api/v1/conversations/{conversation_id}` | conversations | `update_conversation_api_v1_conversations__conversation_id__patch` | Update Conversation |
| `GET` | `/api/v1/documents` | Document Intelligence | `list_documents_api_v1_documents_get` | List all uploaded documents |
| `GET` | `/api/v1/documents/capabilities` | Document Intelligence | `get_capabilities_api_v1_documents_capabilities_get` | Get system PDF processing and OCR capabilities |
| `POST` | `/api/v1/documents/upload` | Document Intelligence | `upload_document_api_v1_documents_upload_post` | Upload an official government PDF for processing |
| `DELETE` | `/api/v1/documents/{document_id}` | Document Intelligence | `delete_document_api_v1_documents__document_id__delete` | Delete a document and all extracted artifacts |
| `GET` | `/api/v1/documents/{document_id}` | Document Intelligence | `get_document_api_v1_documents__document_id__get` | Get full document metadata and processing status |
| `POST` | `/api/v1/documents/{document_id}/ask` | Document Intelligence | `ask_document_api_v1_documents__document_id__ask_post` | Ask a grounded civic question about an uploaded document |
| `GET` | `/api/v1/documents/{document_id}/file` | Document Intelligence | `get_document_file_api_v1_documents__document_id__file_get` | Download or view the original PDF document |
| `POST` | `/api/v1/documents/{document_id}/index` | Document Intelligence | `build_index_api_v1_documents__document_id__index_post` | Build or update vector search index for a document |
| `GET` | `/api/v1/documents/{document_id}/pages` | Document Intelligence | `get_document_pages_api_v1_documents__document_id__pages_get` | Get paginated list of extracted pages |
| `GET` | `/api/v1/documents/{document_id}/pages/{page_number}` | Document Intelligence | `get_document_single_page_api_v1_documents__document_id__pages__page_number__get` | Get extracted text for a specific page |
| `POST` | `/api/v1/documents/{document_id}/retrieve` | Document Intelligence | `retrieve_passages_api_v1_documents__document_id__retrieve_post` | Retrieve candidate passages without generating an answer |
| `POST` | `/api/v1/documents/{document_id}/summary` | Document Intelligence | `generate_document_summary_api_v1_documents__document_id__summary_post` | Generate an AI civic summary of the document |
| `GET` | `/api/v1/gemini/status` | Gemini AI | `get_gemini_status_api_v1_gemini_status_get` | Get Gemini configuration status |
| `POST` | `/api/v1/gemini/test` | Gemini AI | `test_gemini_connection_api_v1_gemini_test_post` | Run diagnostic connectivity test with Gemini |
| `GET` | `/api/v1/grievances` | civic_grievance | `list_grievances_api_v1_grievances_get` | List Grievances |
| `POST` | `/api/v1/grievances/analyze` | civic_grievance | `analyze_grievance_start_api_v1_grievances_analyze_post` | Analyze Grievance Start |
| `GET` | `/api/v1/grievances/capabilities` | civic_grievance | `get_capabilities_api_v1_grievances_capabilities_get` | Get Capabilities |
| `POST` | `/api/v1/grievances/image` | civic_grievance | `upload_grievance_image_api_v1_grievances_image_post` | Upload Grievance Image |
| `DELETE` | `/api/v1/grievances/{id}` | civic_grievance | `delete_grievance_api_v1_grievances__id__delete` | Delete Grievance |
| `GET` | `/api/v1/grievances/{id}` | civic_grievance | `get_grievance_api_v1_grievances__id__get` | Get Grievance |
| `PATCH` | `/api/v1/grievances/{id}` | civic_grievance | `patch_grievance_api_v1_grievances__id__patch` | Patch Grievance |
| `POST` | `/api/v1/grievances/{id}/demo-advance` | civic_grievance | `advance_demo_grievance_status_api_v1_grievances__id__demo_advance_post` | Advance Demo Grievance Status |
| `GET` | `/api/v1/grievances/{id}/image` | civic_grievance | `get_grievance_image_endpoint_api_v1_grievances__id__image_get` | Get Grievance Image Endpoint |
| `POST` | `/api/v1/grievances/{id}/register-demo` | civic_grievance | `register_demo_grievance_api_v1_grievances__id__register_demo_post` | Register Demo Grievance |
| `POST` | `/api/v1/grievances/{id}/retry-analysis` | civic_grievance | `retry_grievance_analysis_api_v1_grievances__id__retry_analysis_post` | Retry Grievance Analysis |
| `GET` | `/api/v1/health` | System & Health | `health_check_api_v1_health_get` | Health check endpoint |
| `GET` | `/api/v1/info` | System & Health | `system_info_api_v1_info_get` | System information & metadata |
| `GET` | `/api/v1/portals` | Official Portals | `list_portals_api_v1_portals_get` | List Portals |
| `POST` | `/api/v1/portals` | Official Portals | `create_portal_api_v1_portals_post` | Create Portal |
| `POST` | `/api/v1/portals/match` | Official Portals | `match_portals_api_v1_portals_match_post` | Match Portals |
| `DELETE` | `/api/v1/portals/{portal_id}` | Official Portals | `delete_portal_api_v1_portals__portal_id__delete` | Delete Portal |
| `GET` | `/api/v1/portals/{portal_id}` | Official Portals | `get_portal_api_v1_portals__portal_id__get` | Get Portal |
| `PATCH` | `/api/v1/portals/{portal_id}` | Official Portals | `update_portal_api_v1_portals__portal_id__patch` | Update Portal |
| `GET` | `/api/v1/preferences` | preferences | `get_preferences_api_v1_preferences_get` | Get Preferences |
| `GET` | `/api/v1/preferences/{key}` | preferences | `get_preference_api_v1_preferences__key__get` | Get Preference |
| `PUT` | `/api/v1/preferences/{key}` | preferences | `set_preference_api_v1_preferences__key__put` | Set Preference |
| `POST` | `/api/v1/services/form-fields/explain` | Public Service Assistant | `explain_form_fields_api_v1_services_form_fields_explain_post` | Explain Form Fields |
| `POST` | `/api/v1/services/form-fields/extract` | Public Service Assistant | `extract_form_fields_api_v1_services_form_fields_extract_post` | Extract Form Fields |
| `POST` | `/api/v1/services/guide` | Public Service Assistant | `generate_service_guide_api_v1_services_guide_post` | Generate Service Guide |
| `DELETE` | `/api/v1/services/guide/{guide_id}` | Public Service Assistant | `delete_service_guide_api_v1_services_guide__guide_id__delete` | Delete Service Guide |
| `GET` | `/api/v1/services/guide/{guide_id}` | Public Service Assistant | `get_service_guide_api_v1_services_guide__guide_id__get` | Get Service Guide |
| `POST` | `/api/v1/services/guide/{guide_id}/retry-analysis` | Public Service Assistant | `retry_service_guide_api_v1_services_guide__guide_id__retry_analysis_post` | Retry Service Guide |
| `GET` | `/api/v1/services/guides` | Public Service Assistant | `list_service_guides_api_v1_services_guides_get` | List Service Guides |
| `GET` | `/api/v1/sources` | Official Sources | `list_official_sources_api_v1_sources_get` | List Official Sources |
| `POST` | `/api/v1/sources` | Official Sources | `upload_official_source_api_v1_sources_post` | Upload Official Source |
| `DELETE` | `/api/v1/sources/{source_id}` | Official Sources | `delete_official_source_api_v1_sources__source_id__delete` | Delete Official Source |
| `GET` | `/api/v1/sources/{source_id}` | Official Sources | `get_official_source_api_v1_sources__source_id__get` | Get Official Source |
| `PATCH` | `/api/v1/sources/{source_id}` | Official Sources | `update_official_source_metadata_api_v1_sources__source_id__patch` | Update Official Source Metadata |
| `GET` | `/api/v1/sources/{source_id}/file` | Official Sources | `get_official_source_file_api_v1_sources__source_id__file_get` | Get Official Source File |
| `POST` | `/api/v1/sources/{source_id}/index` | Official Sources | `rebuild_official_source_index_api_v1_sources__source_id__index_post` | Rebuild Official Source Index |
| `GET` | `/api/v1/sources/{source_id}/pages/{page_number}` | Official Sources | `get_official_source_page_api_v1_sources__source_id__pages__page_number__get` | Get Official Source Page |
| `POST` | `/api/v1/system/backup` | system | `run_backup_api_v1_system_backup_post` | Run Backup |
| `DELETE` | `/api/v1/system/data` | system | `delete_all_data_api_v1_system_data_delete` | Delete All Data |
| `GET` | `/api/v1/system/import-report` | system | `get_import_report_api_v1_system_import_report_get` | Get Import Report |
| `POST` | `/api/v1/system/maintenance` | system | `run_maintenance_api_v1_system_maintenance_post` | Run Maintenance |
| `GET` | `/api/v1/system/resources` | system | `get_system_resources_api_v1_system_resources_get` | Get System Resources |
| `GET` | `/api/v1/system/stats` | system | `get_system_stats_api_v1_system_stats_get` | Get System Stats |
| `GET` | `/api/v1/system/status` | system | `get_system_status_api_v1_system_status_get` | Get System Status |
| `GET` | `/api/v1/verify` | Fact Verification | `list_past_verifications_api_v1_verify_get` | List Past Verifications |
| `POST` | `/api/v1/verify` | Fact Verification | `submit_claim_verification_api_v1_verify_post` | Submit Claim Verification |
| `DELETE` | `/api/v1/verify/{verification_id}` | Fact Verification | `delete_verification_api_v1_verify__verification_id__delete` | Delete Verification |
| `GET` | `/api/v1/verify/{verification_id}` | Fact Verification | `get_verification_status_api_v1_verify__verification_id__get` | Get Verification Status |
| `POST` | `/api/v1/verify/{verification_id}/retry-analysis` | Fact Verification | `retry_verification_analysis_api_v1_verify__verification_id__retry_analysis_post` | Retry Verification Analysis |
| `POST` | `/demo-portal/submit` | Demo Portal | `demo_portal_submit_demo_portal_submit_post` | Controlled Demo Portal Mock Submission |

---

## Security, Authentication & Input Validation Controls

| Domain / Prefix | Rate Limiter | PII Guard | Access / Security Controls |
| :--- | :---: | :---: | :--- |
| `/api/v1/health`, `/api/v1/info` | - | - | Public system probes, zero secret disclosure. |
| `/api/v1/gemini/*` | 5/min | Active | Key masking, model connectivity diagnostics. |
| `/api/v1/documents/*` | 10/min | Active | Max upload 20MB, max 200 pages, UUID validation, traversal immunity. |
| `/api/v1/chat`, `/api/v1/agent/*` | 10/min | Active | XML boundary escaping, evidence ledger, human approval gates. |
| `/api/v1/comparisons/*` | 3/min | Active | Dual PDF alignment, strict clause matching, staged job timeouts. |
| `/api/v1/sources/*` | 5/min | Active | SHA-256 integrity hashing, series tracking, admin gate option. |
| `/api/v1/verifications/*` | 5/min | Active | Tripartite verdict verification, official source cross-check. |
| `/api/v1/portals/*`, `/api/v1/services/*` | 5/min | Active | Verified government URL registry, checklist generation caps. |
| `/api/v1/grievances/*` | 6/min | Active | PII blocking, 25M pixel decompression defense, safe drafting. |
| `/api/v1/browser/*` | 20/min | Active | Playwright isolated demo portal session, strict TTL, orphan process cleanup. |
| `/api/v1/conversations/*`, `/api/v1/activity/*` | - | Active | Parameterized SQLite query persistence, 90-day retention pruning. |
| `/api/v1/system/*` | - | - | Diagnostics, online hot backup, maintenance, memory/thread profiling, confirmation-phrase wipe. |
| `/demo-portal/*` | - | Active | Sandboxed local mock portal simulation; rejects all citizen PII. |
