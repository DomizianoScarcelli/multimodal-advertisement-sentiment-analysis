import json
from torch.utils.data import DataLoader
from config import AUGMENTATION_SIZE, BALANCE_DATASET, DATA_DIR, LENGTH, MODEL_NAME, RANDOM_SEED, STEP
import os
import pickle
import torch
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from datasets.GREX_dataset import GREXDataset
from scipy.interpolate import CubicSpline
from utils.ppg_utils import extract_ppg_features_from_df


class GREXTransform:
    def __init__(self, df):
        self.df = df
        self.transformations = set()

    def jitter(self, data):
        sigma_min, sigma_max = 0.01, 0.2
        sigma = np.random.uniform(sigma_min, sigma_max)
        noise = np.random.normal(loc=0., scale=sigma, size=data.shape)
        return data + noise

    def scaling(self, data):
        sigma_min, sigma_max = 0.01, 0.3
        sigma = np.random.uniform(sigma_min, sigma_max)
        noise = np.random.normal(loc=1., scale=sigma, size=data.shape)
        return data * noise

    def magnitude_warping(self, data):
        sigma_min, sigma_max = 0.1, 0.3
        knot_min, knot_max = 4, 6
        sigma = np.random.uniform(sigma_min, sigma_max)
        knot = np.random.randint(knot_min, knot_max)
        seq_len = data.shape[0]
        step = seq_len // knot
        # Get random curve
        control_points = np.concatenate((np.zeros(1), np.random.normal(
            loc=1.0, scale=sigma, size=(knot - 2)), np.zeros(1)))
        locs = np.arange(0, seq_len, step)

        # Apply cubic spline interpolation
        cs = CubicSpline(locs, control_points)
        return data * cs(np.arange(seq_len))

    def time_shifting(self, data):
        shift = np.random.randint(low=-LENGTH, high=LENGTH)
        return np.roll(data, shift)

    # def window_slicing(self, data):
    #     start = np.random.randint(low=0, high=data.shape[0]//2)
    #     end = start + \
    #         np.random.randint(low=data.shape[0]//2, high=data.shape[0])
    #     sliced_data = data[start:end]

    #     # Calculate the number of zeros to add
    #     pad_length = 2000 - len(sliced_data)

    #     # Pad the sliced data with zeros at the end
    #     padded_data = np.pad(sliced_data, (0, pad_length))

    #     return padded_data

    # def flipping(self, data):
    #     return -data

    def apply(self, item, p=0.5):
        self.transformations = {self.jitter,
                                self.scaling, self.magnitude_warping}

        # subset = [item for item in self.transformations if np.random.rand() < p]
        for transform in self.transformations:
            item = transform(item)
        return item

    def augment(self, n=5_000):
        augmented_data = []
        print(f"Original data: {len(augmented_data)}")
        while len(augmented_data) < n:
            # Randomly select an item from the dataframe
            item = self.df.sample(1).iloc[0]
            ppg, val, aro = item["ppg"], item["val"], item["aro"]
            # Apply transformations and add to augmented_data
            new_item = {"ppg": self.apply(ppg), "val": val, "aro": aro}
            augmented_data.append(new_item)
        print(f"Augmented data: {len(augmented_data)}")
        df = pd.concat([self.df, pd.DataFrame(augmented_data)])
        return df

    def balance(self):
        for class_name in ["val", "aro"]:
            class_counts = self.df[class_name].value_counts()
            max_count = class_counts.max()
            while not all(class_counts == max_count):
                for cls in class_counts.index:
                    cls_count = class_counts[cls]
                    if cls_count < max_count:
                        cls_df = self.df[self.df[class_name] == cls]
                        n_samples = max_count - cls_count
                        samples = cls_df.sample(n_samples, replace=True)
                        # Apply transformations to the new samples
                        samples["ppg"] = samples["ppg"].apply(self.apply)
                        self.df = pd.concat([self.df, samples])
                        class_counts = self.df[class_name].value_counts()
        return self.df


class GREXDataLoader(DataLoader):
    def __init__(self, batch_size):
        self.batch_size = batch_size

        data_segments_path = os.path.join(
            DATA_DIR, "GREX", '3_Physio', 'Transformed')

        annotation_path = os.path.join(
            DATA_DIR, "GREX", '4_Annotation', 'Transformed')

        # NOTE: Important keys here are: "filt_PPG" and "raw_PPG". Sampling rate is 100.
        physio_trans_data_segments = pickle.load(
            open(os.path.join(data_segments_path, "physio_trans_data_segments.pickle"), "rb"))

        # physio_trans_data_session = pickle.load(
        #     open(os.path.join(data_segments_path, "physio_trans_data_session.pickle"), "rb"))

        # with open('session.json', 'w') as f:
        #     json.dump(physio_trans_data_session, f, default=str)
        # with open('segments.json', 'w') as f:
        #     json.dump(physio_trans_data_segments, f, default=str)

        # session_ppg = physio_trans_data_session['filt_PPG']
        # segments_ppg = physio_trans_data_segments['filt_PPG']
        # print(f"Session PPG: {len(session_ppg)}")
        # print(f"Segment PPG: {len(segments_ppg)}")
        # for session in session_ppg:
        #     print(f"Session length: {len(session)}")
        # for segment in segments_ppg:
        #     print(f"Segment length: {len(segment)}")
        # raise ValueError

        # NOTE: Important keys here are: 'ar_seg' and "vl_seg"
        annotations = pickle.load(
            open(os.path.join(annotation_path, "ann_trans_data_segments.pickle"), "rb"))

        self.ppg = torch.tensor(physio_trans_data_segments['filt_PPG'])

        # self.ppg = (self.ppg - self.ppg.mean(dim=0, keepdim=True)
        #             ) / self.ppg.std(dim=0, keepdim=True)

        # self.ppg = self.ppg - self.ppg.min(dim=0, keepdim=True)[0] / \
        #     (self.ppg.max(dim=0, keepdim=True)[
        #      0] - self.ppg.min(dim=0, keepdim=True)[0])

        # assert self.ppg.mean(dim=0).mean() < 1e-6, self.ppg.mean(dim=0).sum()
        # assert self.ppg.std(dim=0).mean() - 1 < 1e-6, self.ppg.std(dim=0).sum()

        self.valence = torch.tensor(annotations['vl_seg']) - 1
        self.arousal = torch.tensor(annotations['ar_seg']) - 1
        self.uncertain = annotations['unc_seg']

        df = []
        for i in range(len(self.ppg)):
            if (self.ppg[i] == 0.0).all():
                continue
            # if self.uncertain[i] is not None and self.uncertain[i] >= 2:
            #     continue
            df.append({"ppg": self.ppg[i].numpy(), "val": int(
                self.valence[i]), "aro": int(self.arousal[i]), "quality_idx": i})

        idx_to_keep = physio_trans_data_segments["PPG_quality_idx"]

        df = pd.DataFrame(df)
        old_len = len(df)
        df = df[df["quality_idx"].isin(idx_to_keep)]
        new_len = len(df)
        print(f"Removed {old_len - new_len} bad quality samples")

        self.data = df

        # old_len = len(self.data)
        # self.data = self.remove_bad_quality_samples(self.data)
        # new_len = len(self.data)
        # print(f"Removed {old_len - new_len} bad quality samples")
        # raise ValueError

        # self.train_df, self.val_df = train_test_split(
        #     self.data, test_size=0.3, stratify=self.data[["val", "aro"]], random_state=RANDOM_SEED)
        # # TODO: just for debug reasons to see if stratify is better, remove later
        # self.test_df = self.val_df

        # self.val_df, self.test_df = train_test_split(
        #     temp_df, test_size=0.1, stratify=temp_df[["val", "aro"]], random_state=RANDOM_SEED)

        self.train_df, temp_df = train_test_split(
            self.data, test_size=0.3, random_state=RANDOM_SEED)
        self.val_df, self.test_df = train_test_split(
            temp_df, test_size=0.5, random_state=RANDOM_SEED)

        if AUGMENTATION_SIZE > 0:
            self.train_df = GREXTransform(
                self.train_df).augment(n=AUGMENTATION_SIZE)

        if BALANCE_DATASET:
            self.train_df = GREXTransform(self.train_df).balance()

        print(
            f"Valence count TRAIN (after balance): {self.train_df['val'].value_counts()}")
        print(
            f"Arousal count TRAIN (after balance): {self.train_df['aro'].value_counts()}")

        print(
            f"Valence count VAL: {self.val_df['val'].value_counts()}")
        print(
            f"Arousal count VAL: {self.val_df['aro'].value_counts()}")

        self.train_df = extract_ppg_features_from_df(self.train_df)
        self.val_df = extract_ppg_features_from_df(self.val_df)
        self.test_df = extract_ppg_features_from_df(self.test_df)

        self.train_df = self.slice_data(self.train_df)
        self.val_df = self.slice_data(self.val_df)
        self.test_df = self.slice_data(self.test_df)

        print(
            f"Valence count VAL: {self.val_df['val'].value_counts()}")
        print(
            f"Arousal count VAL: {self.val_df['aro'].value_counts()}")

        print(
            f"Train: {len(self.train_df)}, Val: {len(self.val_df)}, Test: {len(self.test_df)}")

    def remove_bad_quality_samples(self, df):
        quality_segments_path = os.path.join(
            DATA_DIR, "GREX", '6_Results', 'PPG', 'segments', 'Quality')

        bad_df = pd.read_csv(os.path.join(
            quality_segments_path, "PPG_quality_bad_segments.csv"))

        bad_df['idx'] = bad_df['User'].str.split(
            '_').str[-1].str.extract('(\d+)', expand=False)

        # bad_df.to_csv("bad_quality_ppg.csv", index=False)

        bad_df = bad_df.dropna(subset=['idx'])
        # df.to_csv("all_ppg.csv", index=False)

        # Ensure 'idx' is integer type for comparison
        bad_df['idx'] = bad_df['idx'].astype(int)
        df = df[~df['quality_idx'].isin(bad_df['idx'])]

        # df.to_csv("good_quality_ppg.csv", index=False)
        return df

    def slice_data(self, df, length=LENGTH, step=STEP):
        """
        Taken a dataframe that contains data with columns "ppg", "val", "aro",
        this function outputs a new df where the data is sliced into segments of
        length `length` with a sliding window step of `step`.
        """
        if length > 2000:
            raise ValueError(
                "Length cannot be greater than original length 2000")
        new_df = []
        for _, row in df.iterrows():
            ppg, val, aro = row["ppg"], row["val"], row["aro"]
            for i in range(0, len(ppg) - length, step):
                assert ppg[i:i +
                           length].shape[0] == length, f"Shape is not consistent: {ppg[i:i + length].shape} != {length}"
                segment = ppg[i:i + length]
                new_row = {"ppg": segment, "val": val,
                           "aro": aro, "ppg_features": row["ppg_features"]}
                new_df.append(new_row)
        new_df = pd.DataFrame(new_df)

        # Convert the numpy arrays to PyTorch tensors and concatenate them
        ppg_tensors = torch.cat([torch.from_numpy(x) for x in new_df['ppg']])
        # Calculate the mean and standard deviation
        mean = ppg_tensors.mean()
        std = ppg_tensors.std()
        # Standardize the ppg column
        new_df['ppg'] = new_df['ppg'].apply(lambda x: (
            (torch.from_numpy(x) - mean) / std).numpy())
        return new_df

    def get_train_dataloader(self):
        dataset = GREXDataset(self.train_df)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=True)

    def get_val_dataloader(self):
        dataset = GREXDataset(self.val_df)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=False)

    def get_test_dataloader(self):
        dataset = GREXDataset(self.test_df)
        return DataLoader(dataset, batch_size=self.batch_size, shuffle=False)


if __name__ == "__main__":
    # Test the dataloader
    dataloader = GREXDataLoader(batch_size=32)
    train_loader = dataloader.get_train_dataloader()
    val_loader = dataloader.get_val_dataloader()
    test_loader = dataloader.get_test_dataloader()

    for i, data in enumerate(train_loader):
        print(f"Data size is {len(data)}")
        pgg, features, (val, ar) = data
        print(f"Batch {i}: {pgg.shape}, {val.shape}, {ar.shape}")
        break
