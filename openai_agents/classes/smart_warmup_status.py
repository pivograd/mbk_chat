from dataclasses import dataclass, field
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Optional

from openai_agents.classes.conversation_result import ConversationResult


@dataclass
class SmartWarmupStats:
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    total_conversations: int = 0
    by_status: Counter = field(default_factory=Counter)
    by_inbox: dict[int, Counter] = field(default_factory=lambda: defaultdict(Counter))

    sent_conv_ids: list[int] = field(default_factory=list)
    completed_conv_ids: list[int] = field(default_factory=list)
    wait_date_conv_ids: list[int] = field(default_factory=list)
    errors: list[tuple[int, str]] = field(default_factory=list)

    def register(self, inbox_id: int, result: ConversationResult) -> None:
        self.total_conversations += 1
        self.by_status[result.status] += 1
        self.by_inbox[inbox_id][result.status] += 1

        if result.status == 'sent':
            self.sent_conv_ids.append(result.conv_id)
        elif result.status == 'completed':
            self.completed_conv_ids.append(result.conv_id)
        elif result.status == 'wait_date':
            self.wait_date_conv_ids.append(result.conv_id)
        elif result.status == 'error':
            self.errors.append((result.conv_id, result.message))

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc)

    def _format_ids(self, ids: list[int], limit: int = 50) -> str:
        # чтобы не взорвать телеграм при больших количествах
        if not ids:
            return '-'
        if len(ids) <= limit:
            return ', '.join(map(str, ids))
        head = ', '.join(map(str, ids[:limit]))
        return f'{head}, ... (ещё {len(ids) - limit})'

    def format_summary(self) -> str:
        if not self.finished_at:
            self.finish()

        lines = [
            '[smart_warm_up] Статистика прогона крона',
            f'Период: {self.started_at.isoformat()} — {self.finished_at.isoformat()}',
            '',
            f'Всего диалогов в обработке: {self.total_conversations}',
            f'  • Отправили рассылку: {self.by_status["sent"]}',
            f'  • Завершили диалогов: {self.by_status["completed"]}',
            f'  • Ждём дату следующей рассылки: {self.by_status["wait_date"]}',
            f'  • Пропущено по другим причинам: {self.by_status["skipped"]}',
            f'  • Ошибок: {self.by_status["error"]}',
            f'  • Странных исходов: {self.by_status["unexpected"]}',
            '',
            f'Диалоги с рассылкой ({self.by_status["sent"]}): '
            f'{self._format_ids(self.sent_conv_ids)}',
            f'Завершённые диалоги ({self.by_status["completed"]}): '
            f'{self._format_ids(self.completed_conv_ids)}',
            f'Диалоги, где ждём дату ({self.by_status["wait_date"]}): '
            f'{self._format_ids(self.wait_date_conv_ids)}',
        ]

        if self.errors:
            lines.append('')
            lines.append('Ошибки по диалогам:')
            for conv_id, msg in self.errors:
                lines.append(f'  • {conv_id}: {msg}')

        lines.append('')
        lines.append('Разбивка по инбоксам:')
        for inbox_id, cnt in self.by_inbox.items():
            total_inbox = sum(cnt.values())
            lines.append(
                f'  inbox {inbox_id}: total={total_inbox}, '
                f'sent={cnt["sent"]}, completed={cnt["completed"]}, '
                f'wait_date={cnt["wait_date"]}, skipped={cnt["skipped"]}, '
                f'error={cnt["error"]}'
            )

        return '\n'.join(lines)
