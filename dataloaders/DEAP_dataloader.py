from config import (
    DATA_DIR,
    LENGTH,
    RANDOM_SEED,
    STEP,
    WT
)
import pickle
from shared.constants import CEAP_MEAN, CEAP_STD
from torch.utils.data import DataLoader
from tqdm import tqdm
from typing import List
import os
import torch
import numpy as np
import pandas as pd
from datasets.DEAP_dataset import DEAPDataset
from utils.ppg_utils import wavelet_transform
from sklearn.model_selection import train_test_split, GroupShuffleSplit

# Sample rate is 128hz
# Signals are 8064 long
# Each signal is 63 seconds long

class DEAPDataLoader(DataLoader):
    def __init__(self,
                 batch_size: int):
        self.batch_size = batch_size
        self.data = self.load_data()
        # self.data["valence"] = self.data["valence"].apply(lambda x: self.discretize_labels(torch.tensor(x)))
        self.data["valence"] = self.data["valence"].apply(lambda x: round(x))

        #Standardize
        self.data["ppg"] = self.data["ppg"].apply(lambda x: np.array(x))
        print(f"Shape of signal is: {self.data['ppg'].iloc[0].shape}")
        cat_data = np.concatenate(self.data["ppg"], axis=0)
        mean, std = cat_data.mean(), cat_data.std()
        print(f"Before DEAP mean + std: {mean, std}")
        self.data["ppg"] = self.data["ppg"].apply(lambda x: (x-mean)/std) 
        cat_data = np.concatenate(self.data["ppg"], axis=0)
        mean, std = cat_data.mean(), cat_data.std()
        print(f"Normalized DEAP mean + std: {mean, std}")

        self.train_df, self.val_df, self.test_df = self.split_data()
        self.train_df = self.slice_data(self.train_df)
        self.val_df = self.slice_data(self.val_df)
        self.test_df = self.slice_data(self.test_df)

        if WT:
            print(f"Performing wavelet transform...")
            tqdm.pandas()
            self.train_df["ppg"] = self.train_df["ppg"].progress_apply(wavelet_transform)
            self.val_df["ppg"] = self.val_df["ppg"].progress_apply(wavelet_transform)
            self.test_df["ppg"] = self.test_df["ppg"].progress_apply(wavelet_transform)
        else:
            print("Skipped wavelet transform")

        print(f"Train_df length: {len(self.train_df)}")
        print(f"Val_df length: {len(self.val_df)}")
        print(f"Test_df length: {len(self.test_df)}")

        # target_count = label_counts.min()
        # # Sample function to get balanced sample from each group
        # def balanced_sample(group):
        #   return group.sample(target_count, random_state=RANDOM_SEED)
        # # Apply sample function to each group in the DataFrame 
        # self.data = self.data.groupby('valence').apply(balanced_sample)

    def load_data(self) -> pd.DataFrame:
        data_dir = os.path.join(DATA_DIR, "DEAP", "data")
        # metadata_dir = os.path.join(DATA_DIR, "DEAP", "metadata")
        ppg_channel = 39
        df = []

        for file in os.listdir(data_dir):
            if not file.endswith(".dat"):
                continue
            abs_path = os.path.join(data_dir, file)
            print(f"reading file: {abs_path}")
            with open(abs_path, "rb") as f:
                # resolve the python 2 data problem by encoding : latin1
                subject = pickle.load(f, encoding='latin1')
                for trial_i in range(40):
                    # NOTE: valence is in range [1,9]
                    valence: np.ndarray = subject["labels"][trial_i][0] #index 0 is valence, 1 arousal
                    data: np.ndarray = subject["data"][trial_i][ppg_channel]
                    df.append({"ppg": data, "valence": valence})
        return pd.DataFrame(df)

    def split_data(self):
        train_df, temp_df = train_test_split(self.data, test_size=0.2, random_state=RANDOM_SEED)
        val_df, test_df = train_test_split(temp_df, test_size=0.5, random_state=RANDOM_SEED)
        return train_df, val_df, test_df

        # NOTE: split by subjects
        df = self.data

        train_ratio = 0.6
        val_ratio = 0.2
        test_ratio = 0.2
        if train_ratio + val_ratio + test_ratio != 1:
            raise ValueError("Ratios must sum to 1. Please adjust the values.")

        pid_groups = df['participant_id'].tolist()
        X = df['ppg'].tolist()
        Y = df['valence'].tolist()
        sss = GroupShuffleSplit(n_splits=1, test_size=val_ratio + test_ratio, random_state=RANDOM_SEED)

        # Split the dataframe based on pid groups
        for train_index, test_index in sss.split(X, Y, pid_groups):  # Splitting based on labels maintains class balance
            train_df = df.iloc[train_index]
            remaining = df.iloc[test_index]

            # Further split remaining data into validation and test sets (optional)
            sss_inner = GroupShuffleSplit(n_splits=1, test_size=test_ratio / (val_ratio + test_ratio), random_state=RANDOM_SEED)
            X_remaining, Y_remaining = remaining["ppg"].tolist(), remaining["valence"].tolist()    
            pid_groups_remaining = remaining['participant_id'].tolist()
            val_index, test_index = next(sss_inner.split(X_remaining, Y_remaining, pid_groups_remaining))
            val_df = remaining.iloc[val_index]
            test_df = remaining.iloc[test_index]

        train_pids = set(train_df["participant_id"].unique())
        val_pids = set(val_df["participant_id"].unique())
        test_pids = set(test_df["participant_id"].unique())
        
        # print("train pids ", train_pids)
        # print("val pids ", val_pids)
        # print("test pids ",test_pids )

        assert len(train_pids & val_pids) == 0
        assert len(train_pids & test_pids) == 0
        assert len(val_pids & test_pids) == 0
         
        return train_df, val_df, test_df

    def slice_data(self, df, length=LENGTH, step=STEP) -> pd.DataFrame:
        if length > 3000:
            raise ValueError(f"Length cannot be greater than original length")
        new_df = []
        for _, row in df.iterrows():
            ppg, label = row["ppg"], row["valence"]
            for i in range(0, len(ppg) - length + 1, step):
                ppg_segment = ppg[i:i+length]
                new_row = {
                        "ppg": ppg_segment ,
                        "valence": label,
                        "segment": i}
                new_df.append(new_row)
        new_df = pd.DataFrame(new_df)
        return new_df
    
    def discretize_labels(self, valence: torch.Tensor) -> List[float]:
        self.labels = torch.full_like(valence, -1)
        self.labels[(valence >= 1) & (valence <= 4) ] = 0 
        self.labels[(valence > 4) & (valence <= 6) ] = 1
        self.labels[(valence > 6) & (valence <= 9) ] = 2
        return self.labels.tolist()

    def get_train_dataloader(self):
        dataset = DEAPDataset(self.train_df)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

    def get_val_dataloader(self):
        dataset = DEAPDataset(self.val_df)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=False)

    def get_test_dataloader(self):
        dataset = DEAPDataset(self.test_df)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=False)


if __name__ == "__main__":
    # Test the dataloader
    dataloader = DEAPDataLoader(batch_size=32)
    # test_loader = dataloader.get_test_dataloader()

    # for i, data in enumerate(test_loader):
    #     print(f"Data size is {len(data)}")
    #     break
