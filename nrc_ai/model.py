"""Torch policy/value model for history-conditioned supervised warm-starting."""

from __future__ import annotations

from typing import Optional

import torch
from torch import Tensor, nn


class RecurrentPolicyValue(nn.Module):
    def __init__(self, input_dim: int, action_dim: int, hidden_dim: int = 128) -> None:
        super().__init__()
        self.input_dim = input_dim
        self.action_dim = action_dim
        self.hidden_dim = hidden_dim
        self.encoder = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.Tanh())
        self.gru = nn.GRU(hidden_dim, hidden_dim, batch_first=True)
        self.policy = nn.Linear(hidden_dim, action_dim)
        self.value = nn.Linear(hidden_dim, 1)

    def forward(self, sequence: Tensor, hidden: Optional[Tensor] = None) -> tuple[Tensor, Tensor, Tensor]:
        encoded = self.encoder(sequence)
        recurrent, hidden = self.gru(encoded, hidden)
        logits = self.policy(recurrent)
        values = torch.tanh(self.value(recurrent).squeeze(-1))
        return logits, values, hidden


def masked_policy_loss(logits: Tensor, target: Tensor, legal_mask: Tensor) -> Tensor:
    masked = logits.masked_fill(~legal_mask.bool(), -1e9)
    return nn.functional.cross_entropy(masked, target)
