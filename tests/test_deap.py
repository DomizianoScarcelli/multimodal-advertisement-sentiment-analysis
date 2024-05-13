from utils.utils import save_results, set_seed, select_device
from config import *
from torchmetrics import Accuracy, Recall
from tqdm import tqdm
import torch
import torch.nn as nn
import os
import json
from dataloaders.DEAP_dataloader import DEAPDataLoader
from models.EmotionNetCEAP import EmotionNet, Encoder, Decoder
from packages.rppg_toolbox.main import run_single
from utils.ppg_utils import wavelet_transform
from shared.constants import CEAP_MEAN, CEAP_STD
from packages.rppg_toolbox.utils.plot import plot_signal
from fusion.ppg_processing import main as ppg_main


def test_loop(model, test_loader, device, model_path, criterion, num_classes):
    model.eval()
    losses = []
    accuracy_metric = Accuracy(task="multiclass", num_classes=num_classes).to(device)
    recall_metric = Recall(
        task="multiclass", num_classes=num_classes, average="macro"
    ).to(device)

    with torch.no_grad():  # Disable gradient calculation for efficiency
        for batch in tqdm(test_loader, desc="Testing", leave=False):
            src, target = batch["ppg"], batch["valence"]

            src = src.float().to(device)
            target = target.float().to(device)

            src = src.permute(1, 0, 2)
            target = target.permute(1, 0)

            output = model(src, target, 0)  # turn off teacher forcing
            output_dim = output.shape[-1]
            output = output[1:].view(-1, output_dim)
            trg = target[1:].reshape(-1)
            loss = criterion(output, trg)
            losses.append(loss.item())

            preds = output.argmax(dim=1)
            accuracy_metric.update(preds, trg)
            recall_metric.update(preds, trg)

        test_results = {
            "test_loss": torch.tensor(losses).mean().item(),
            "test_accuracy": accuracy_metric.compute().item(),
            "test_recall": recall_metric.compute().item(),
        }

        print(
            f"Test | Loss: {torch.tensor(losses).mean():.4f} | Accuracy: {(accuracy_metric.compute() * 100):.4f} | Recall: {(recall_metric.compute() * 100):.4f}"
        )

        if SAVE_RESULTS:
            save_results(model_path, test_results, test=True)


def test_loop_deap(model, device, model_path, num_classes):
    test_loader = DEAPDataLoader(batch_size=32).get_test_dataloader()
    criterion = nn.CrossEntropyLoss()

    model.eval()
    losses = []
    accuracy_metric = Accuracy(task="multiclass", num_classes=num_classes).to(device)
    recall_metric = Recall(
        task="multiclass", num_classes=num_classes, average="macro"
    ).to(device)
    
    pbar = tqdm(test_loader, desc="Testing")
    with torch.no_grad():  # Disable gradient calculation for efficiency
        for batch in test_loader:
            pbar.update(1)
            src, target = batch["ppg"], batch["valence"]

            src = src.float().to(device)
            target = target.float().to(device)

            src = src.permute(1, 0, 2)

            
            # print(f"target shape is: {target.shape}")
            output = model(src, target, 0)  # turn off teacher forcing
            output = output[1:]

            # print(f"output shape is: {output.shape}")
            # Get the mean emotion between all the timesteps
            output_mean = output.mean(dim=0)
            # output_mean = output[-1, :]
            # print(f"output mean shape is: {output_mean.shape}")

            loss = criterion(output_mean, target.long())
            losses.append(loss.item())

            preds = output_mean.argmax(dim=-1)
            # print(f"argmaxed output_mean shape: {preds.shape}")
            accuracy_metric.update(preds, target)
            recall_metric.update(preds, target)
            pbar.set_postfix_str(f"Test | Loss: {torch.tensor(losses).mean():.2f} | Acc: {(accuracy_metric.compute() * 100):.2f} | Rec: {(recall_metric.compute() * 100):.2f}")

        print(
            f"Test | Loss: {torch.tensor(losses).mean():.4f} | Accuracy: {(accuracy_metric.compute() * 100):.4f} | Recall: {(recall_metric.compute() * 100):.4f}"
        )


def get_model_and_dataloader(model_path, device):
    # Load configuration
    conf_path = PATH_TO_SAVE_RESULTS + f"/{model_path}/configurations.json"
    configurations = None
    if os.path.exists(conf_path):
        print(
            "--Model-- Old configurations found. Using those configurations for the test."
        )
        with open(conf_path, "r") as json_file:
            configurations = json.load(json_file)
    else:
        print(
            "--Model-- Old configurations NOT found. Using configurations in the config for test."
        )

    input_dim = LENGTH // WAVELET_STEP if WT else 1
    output_dim = 3
    encoder_embedding_dim = LENGTH // WAVELET_STEP if WT else 1
    decoder_embedding_dim = LENGTH // WAVELET_STEP if WT else 1
    hidden_dim = (
        LSTM_HIDDEN
        if configurations is None
        else configurations["lstm_config"]["num_hidden"]
    )
    n_layers = (
        LSTM_LAYERS
        if configurations is None
        else configurations["lstm_config"]["num_layers"]
    )
    encoder_dropout = DROPOUT_P
    decoder_dropout = DROPOUT_P
    num_classes = EMOTION_NUM_CLASSES

    encoder = Encoder(
        input_dim,
        encoder_embedding_dim,
        hidden_dim,
        n_layers,
        encoder_dropout,
    )

    decoder = Decoder(
        output_dim,
        decoder_embedding_dim,
        hidden_dim,
        n_layers,
        decoder_dropout,
    )

    model = EmotionNet(encoder, decoder).to(device)
    return model, num_classes


def load_test_model(model, model_path, epoch, device):
    state_dict = torch.load(
        f"{PATH_TO_SAVE_RESULTS}/{model_path}/models/mi_project_{epoch}.pt",
        map_location=device,
    )
    model.load_state_dict(state_dict)
    model.eval()
    return model


def test_from_video(model_path, epoch):
    video_path = "/Users/dov/Library/Mobile Documents/com~apple~CloudDocs/dovsync/Documenti Universita/Multimodal Interaction/Project/multimodal-interaction-project/packages/rppg_toolbox/data/InferenceVideos/RawData/video1/video.mp4"
    return ppg_main(model_path=model_path, epoch=epoch, video_frames=video_path)


def test_from_deap_videos():
    """
    Given the DEAP videos from which the PPG signal is extracted, we extract
    the PPG with the rppg_toolbox library and compare it to the ground truth
    signal to have an rPPG evaluation.
    """
    deap_videos_dir = os.path.join(DATA_DIR, "DEAP", "videos")
    for v_file in os.listdir(deap_videos_dir):
        if not v_file.endswith(".avi"): continue
        #TODO: implement
         

    pass


def main(model_path, epoch):
    set_seed(RANDOM_SEED)
    device = select_device()
    model, num_classes = get_model_and_dataloader(model_path, device)
    print(f"Num classes is: {num_classes}")
    model = load_test_model(model, model_path, epoch, device)

    # test_loader = dataloader.get_test_dataloader()
    # criterion = torch.nn.CrossEntropyLoss()
    # test_loop(model, test_loader, device, model_path, criterion, num_classes)
    test_loop_deap(model, device, model_path, num_classes)
    # test_from_video(model)


if __name__ == "__main__":
    # Name of the sub-folder into "results" folder in which to find the model to test (e.g. "resnet34_2023-12-10_12-29-49")
    model_path = "EmotionNet - LSTM Seq2Seq_2024-05-01_13-11-39"
    epoch = "204"
    # model_path = "EmotionNet - LSTM Seq2Seq_2024-05-11_18-10-59"
    # epoch = "19"
    # main(model_path, epoch)
    test_from_video(model_path, epoch)
