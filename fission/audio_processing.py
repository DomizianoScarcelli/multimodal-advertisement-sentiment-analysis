from config import AUDIO_SAMPLE_RATE, AUDIO_OFFSET, AUDIO_DURATION, DROPOUT_P, LSTM_HIDDEN_SIZE, LSTM_NUM_LAYERS, NUM_MFCC, FRAME_LENGTH, HOP_LENGTH, PATH_TO_SAVE_RESULTS, RAVDESS_NUM_CLASSES, RANDOM_SEED
from models.AudioNetCT import AudioNet_CNN_Transformers as AudioNetCT
from models.AudioNetCL import AudioNet_CNN_LSTM as AudioNetCL
from utils.audio_utils import extract_mfcc_features, extract_waveform_from_audio_file, extract_features
from utils.utils import upload_scaler, select_device, set_seed
import numpy as np
import torch
import json
import os

from utils.utils import upload_scaler

def main(model_path, audio_file_path, epoch):
    set_seed(RANDOM_SEED)
    device = select_device()
    type = model_path.split('_')[0]
    model, scaler, _ = get_model_and_dataloader(model_path, device, type)
    model = load_test_model(model, model_path, epoch, device)
    waveform = extract_audio_features(audio_file_path, scaler)
    waveform = torch.from_numpy(waveform).float()
    output = model(waveform.to(device))
    pred = torch.argmax(output, -1).detach()
    print(pred.item())

def extract_audio_features(audio_file_path, scaler):
    # Load the audio file
    waveform = extract_waveform_from_audio_file(file=audio_file_path, desired_length_seconds=AUDIO_DURATION, offset=AUDIO_OFFSET, desired_sample_rate=AUDIO_SAMPLE_RATE)
    # Extract features from the audio file
    # features = extract_features(waveform=waveform, sample_rate=AUDIO_SAMPLE_RATE, n_mfcc=NUM_MFCC, n_fft=1024, win_length=512, n_mels=128, window='hamming', frame_length=FRAME_LENGTH, hop_length=HOP_LENGTH)
    features = extract_mfcc_features(waveform, sample_rate=AUDIO_SAMPLE_RATE, n_mfcc=NUM_MFCC, n_fft=1024, win_length=512, n_mels=128, window='hamming')
    # Scale the waveform
    features = scale_waveform(features, scaler)
    features = np.expand_dims(np.expand_dims(features, axis=0), axis=0) # Add channel dimension to get a 4D tensor suitable for CNN
    return features

def scale_waveform(waveform, scaler):
    return scaler.transform(waveform.reshape(-1, waveform.shape[-1])).reshape(waveform.shape)

def load_test_model(model, model_path, epoch, device):
    state_dict = torch.load(
        f"{PATH_TO_SAVE_RESULTS}/{model_path}/models/mi_project_{epoch}.pt", map_location=device)
    model.load_state_dict(state_dict)
    model.eval()
    return model

def get_model_and_dataloader(model_path, device, type):
    # Load configuration
    conf_path = PATH_TO_SAVE_RESULTS + f"/{model_path}/configurations.json"
    configurations = None
    if os.path.exists(conf_path):
        print(
            "--Model-- Old configurations found. Using those configurations for the test.")
        with open(conf_path, 'r') as json_file:
            configurations = json.load(json_file)
    else:
        print("--Model-- Old configurations NOT found. Using configurations in the config for test.")

    # Load model
    model = None
    scaler = None
    if type == "AudioNetCT":
        num_classes = RAVDESS_NUM_CLASSES if configurations is None else configurations["num_classes"]
        num_mfcc = NUM_MFCC if configurations is None else configurations["num_mfcc"]
        dropout_p = DROPOUT_P if configurations is None else configurations["dropout_p"]
        model = AudioNetCT(
            num_classes=num_classes, num_mfcc=num_mfcc, dropout_p=dropout_p).to(device)
        scaler = upload_scaler(model_path)
    elif type == "AudioNetCL":
        num_classes = RAVDESS_NUM_CLASSES if configurations is None else configurations["num_classes"]
        num_mfcc = NUM_MFCC if configurations is None else configurations["num_mfcc"]
        lstm_hidden_size = LSTM_HIDDEN_SIZE if configurations is None else configurations["lstm_hidden_size"]
        lstm_num_layers = LSTM_NUM_LAYERS if configurations is None else configurations["lstm_num_layers"]
        dropout_p = DROPOUT_P if configurations is None else configurations["dropout_p"]
        model = AudioNetCL(
            num_classes=num_classes, num_mfcc=num_mfcc, num_layers=lstm_num_layers, hidden_size=lstm_hidden_size, dropout_p=dropout_p).to(device)
        scaler = upload_scaler(model_path)
    else:
        raise ValueError(f"Unknown architecture {type}")
    return model, scaler, num_classes

if __name__ == "__main__":
    epoch = 498
    model_path = os.path.join("AudioNetCT_2024-03-26_16-05-55")
    audio_file_path = os.path.join("data", "AUDIO", "audio_ravdess_files", "03-01-01-01-01-01-01.wav")
    main(model_path=model_path, audio_file_path=audio_file_path, epoch=epoch)