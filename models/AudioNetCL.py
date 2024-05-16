from config import DROPOUT_P, LSTM_HIDDEN_SIZE, LSTM_NUM_LAYERS, EMOTION_NUM_CLASSES
import torch.nn as nn
import torch

class AudioNet_CNN_LSTM(nn.Module):
    def __init__(self, input_dim, num_layers=LSTM_NUM_LAYERS, hidden_size=LSTM_HIDDEN_SIZE, dropout=DROPOUT_P, num_classes = EMOTION_NUM_CLASSES):
        super().__init__() 
        self.lstm = nn.LSTM(input_size=input_dim,
                            hidden_size=hidden_size,
                            num_layers=num_layers,
                            batch_first=True,
                            dropout=dropout,
                            bidirectional=False
                            )
        self.CNN_block = nn.Sequential(
            nn.Conv2d(
                in_channels=1,
                out_channels=16,
                kernel_size=3,
                stride=1,
                padding=1
                      ),
            nn.BatchNorm2d(16),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=2, stride=2),
            nn.Dropout(p=dropout),
            nn.Conv2d(
                in_channels=16, 
                out_channels=32,
                kernel_size=3,
                stride=1,
                padding=1
                      ),
            nn.BatchNorm2d(32),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=4, stride=4),
            nn.Dropout(p=dropout), 
            nn.Conv2d(
                in_channels=32,
                out_channels=64,
                kernel_size=3,
                stride=1,
                padding=1
                      ),
            nn.BatchNorm2d(64),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=4, stride=4),
            nn.Dropout(p=dropout),
        )

        self.fc = nn.Linear((512+hidden_size), num_classes) 
        
    def forward(self, x):
        CNN_embedding = self.CNN_block(x)
        CNN_embedding = torch.flatten(CNN_embedding, start_dim=1) 

        x_lstm = torch.squeeze(x, 1)
        x_lstm = x_lstm.permute(0, 2, 1)
        lstm_output, _ = self.lstm(x_lstm)
        lstm_embedding = lstm_output[:, -1, :]

        complete_embedding = torch.cat([CNN_embedding, lstm_embedding], dim=1)
        output_logits = self.fc(complete_embedding)  
        return output_logits
