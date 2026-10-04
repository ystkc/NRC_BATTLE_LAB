"""Minimal policy/value warm-start training over versioned episodes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

import numpy as np
import torch
from torch import nn

from .encoding import JsonObservationEncoder
from .model import RecurrentPolicyValue
from .replay import Episode


@dataclass(frozen=True)
class TrainingMetrics:
    policy_loss: float
    value_loss: float
    action_accuracy: float
    steps: int


def _episode_tensors(episode: Episode, encoder: JsonObservationEncoder, action_index: Mapping[str, int], action_dim: int):
    if not episode.steps:
        raise ValueError("cannot train on an empty episode")
    features = np.stack([encoder.encode(step.observation) for step in episode.steps])
    targets = np.array([action_index[step.action_key] for step in episode.steps], dtype=np.int64)
    policy_targets = np.zeros((len(episode.steps), action_dim), dtype=np.float32)
    masks = np.zeros((len(episode.steps), action_dim), dtype=np.bool_)
    for row, step in enumerate(episode.steps):
        for key in step.legal_action_keys:
            if key in action_index:
                masks[row, action_index[key]] = True
        if step.search_policy:
            for key, probability in step.search_policy.items():
                if key in action_index and masks[row, action_index[key]]:
                    policy_targets[row, action_index[key]] = max(0.0, float(probability))
            total = float(policy_targets[row].sum())
            if total > 0.0:
                policy_targets[row] /= total
        if not policy_targets[row].any():
            policy_targets[row, targets[row]] = 1.0
    if not masks.any(axis=1).all():
        raise ValueError("every training step must have at least one indexed legal action")
    has_terminal_value = episode.terminal_winner in (0, 1) and not episode.truncated
    winner_value = 1.0 if episode.terminal_winner == 0 else -1.0
    values = np.full(len(episode.steps), winner_value, dtype=np.float32)
    value_mask = np.full(len(episode.steps), has_terminal_value, dtype=np.float32)
    return (torch.from_numpy(features).unsqueeze(0), torch.from_numpy(targets), torch.from_numpy(policy_targets), torch.from_numpy(masks), torch.from_numpy(values), torch.from_numpy(value_mask))


def train_policy_value(model: RecurrentPolicyValue, episodes: Iterable[Episode], action_keys: list[str], *, encoder: JsonObservationEncoder | None = None, epochs: int = 1, learning_rate: float = 3e-4, device: str = "cpu") -> TrainingMetrics:
    episodes = list(episodes)
    if not episodes:
        raise ValueError("at least one episode is required")
    if model.action_dim != len(action_keys):
        raise ValueError("model action_dim must equal action_keys length")
    encoder = encoder or JsonObservationEncoder(model.input_dim)
    action_index = {key: index for index, key in enumerate(action_keys)}
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    model.to(device)
    total_policy = total_value = total_correct = 0.0
    total_steps = 0
    model.train()
    for _ in range(epochs):
        for episode in episodes:
            features, targets, policy_targets, masks, values, value_mask = _episode_tensors(episode, encoder, action_index, len(action_keys))
            features, targets, policy_targets, masks, values, value_mask = (item.to(device) for item in (features, targets, policy_targets, masks, values, value_mask))
            optimizer.zero_grad()
            logits, predicted_values, _ = model(features)
            logits = logits[0]
            predicted_values = predicted_values[0]
            masked_logits = logits.masked_fill(~masks, -1e9)
            log_policy = nn.functional.log_softmax(masked_logits, dim=-1)
            policy_loss = -(policy_targets * log_policy).sum(dim=-1).mean()
            value_error = (predicted_values - values).pow(2)
            value_loss = (value_error * value_mask).sum() / value_mask.sum().clamp_min(1.0)
            (policy_loss + value_loss).backward()
            optimizer.step()
            total_policy += float(policy_loss.detach()) * len(targets)
            total_value += float(value_loss.detach()) * len(targets)
            total_correct += float((masked_logits.argmax(dim=-1) == targets).sum())
            total_steps += len(targets)
    return TrainingMetrics(total_policy / total_steps, total_value / total_steps, total_correct / total_steps, total_steps)
