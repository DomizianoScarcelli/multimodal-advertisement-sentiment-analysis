import torch
from config import AUGMENTATION_SIZE, EMOTION_NUM_CLASSES, LENGTH, RANDOM_SEED, STEP, USE_WANDB, VAL_SIZE, LIMIT, MODEL_NAME, BATCH_SIZE, LR, N_EPOCHS, METADATA_CSV, REG, FER_NUM_CLASSES, DROPOUT_P, RESUME_TRAINING, PATH_TO_SAVE_RESULTS, PATH_MODEL_TO_RESUME, RESUME_EPOCH, BALANCE_DATASET, DATASET_NAME
from dataloaders.GREX_dataloader import GREXDataLoader
from train.loops.train_loop_emotion_single import train_eval_loop
from utils.utils import set_seed, select_device
from models.EmotionNetCL import EmotionNet
from models.PreProcessedEmotionNet import PreProcessedEmotionNet


def main():
    set_seed(RANDOM_SEED)
    device = select_device()
    loader = GREXDataLoader(batch_size=BATCH_SIZE)

    train_loader = loader.get_train_dataloader()
    val_loader = loader.get_val_dataloader()

    model_aro = EmotionNet(num_classes=EMOTION_NUM_CLASSES,
                           dropout=DROPOUT_P).to(device)
    model_val = EmotionNet(num_classes=EMOTION_NUM_CLASSES,
                           dropout=DROPOUT_P).to(device)
    model = [model_aro, model_val]

    # if RESUME_TRAINING:
    #     model.load_state_dict(torch.load(
    #         f"{PATH_TO_SAVE_RESULTS}/{PATH_MODEL_TO_RESUME}/models/mi_project_{RESUME_EPOCH}.pt"))
    optimizer_aro = torch.optim.Adam(model_aro.parameters(),
                                     lr=LR,
                                     weight_decay=REG)

    optimizer_val = torch.optim.Adam(model_val.parameters(),
                                     lr=LR,
                                     weight_decay=REG)

    optimizer = [optimizer_aro, optimizer_val]

    # scheduler = torch.optim.lr_scheduler.OneCycleLR(
    #     optimizer=optimizer,
    #     max_lr=LR,
    #     epochs=N_EPOCHS,
    #     steps_per_epoch=len(train_loader))
    scheduler = None

    criterion = torch.nn.CrossEntropyLoss()

    config = {
        "architecture": "EmotionNet - CNN + LSTM",
        "scope": "EmotionNet",
        "learning_rate": LR,
        "epochs": N_EPOCHS,
        "reg": REG,
        "batch_size": BATCH_SIZE,
        "num_classes": EMOTION_NUM_CLASSES,
        "dataset": "GREX",
        "optimizer": "AdamW",
        "resumed": RESUME_TRAINING,
        "use_wandb": USE_WANDB,
        "balance_dataset": BALANCE_DATASET,
        "limit": LIMIT,
        "length": LENGTH,
        "step": STEP,
        "dropout_p": DROPOUT_P,
        "agumented_data": AUGMENTATION_SIZE,
        "message": "",

    }

    train_eval_loop(device=device,
                    train_loader=train_loader,
                    val_loader=val_loader,
                    models=model,
                    config=config,
                    optimizers=optimizer,
                    scheduler=scheduler,
                    criterion=criterion,
                    scaler=None,
                    resume=RESUME_TRAINING)


if __name__ == "__main__":
    main()
