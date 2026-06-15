import torch
from torch import nn
from torchvision.models import mobilenet_v2


class FightCNNLSTM(nn.Module):
    def __init__(self, hidden_size: int = 128, num_layers: int = 1) -> None:
        super().__init__()
        backbone = mobilenet_v2(weights=None)
        self.features = nn.Sequential(backbone.features, nn.AdaptiveAvgPool2d((1, 1)))
        self.feature_dim = 1280
        self.lstm = nn.LSTM(self.feature_dim, hidden_size, num_layers=num_layers, batch_first=True, bidirectional=True)
        self.classifier = nn.Sequential(nn.Dropout(0.30), nn.Linear(hidden_size * 2, 1))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: B, T, C, H, W
        batch, steps, channels, height, width = x.shape
        x = x.reshape(batch * steps, channels, height, width)
        features = self.features(x).flatten(1)
        features = features.reshape(batch, steps, -1)
        output, _ = self.lstm(features)
        pooled = output.mean(dim=1)
        return self.classifier(pooled).squeeze(1)
