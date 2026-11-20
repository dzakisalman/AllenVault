# bot/conversation.py
# ConversationHandler states untuk Phase 3+ (transaction flow)
# Disiapkan strukturnya sekarang agar mudah diisi nanti.

# State IDs
(
    STATE_WAITING_AMOUNT,
    STATE_WAITING_CATEGORY,
    STATE_WAITING_ACCOUNT,
    STATE_WAITING_DESCRIPTION,
    STATE_WAITING_DATE,
    STATE_CONFIRMING,
    STATE_EDITING,
) = range(7)

