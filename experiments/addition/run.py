import tensorflow as tf
import wandb
import os
import sys
import argparse
import multiprocessing as mp
from pathlib import Path

PARENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(PARENT_DIR / "../.."))

from experiments.addition.classifier import SumClassifier
from experiments.addition.data.generation import create_loader
from trainer import Trainer
from evaluate import sum_accuracy


os.environ["CUDA_VISIBLE_DEVICES"] = "0"
os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"


def train(digits_per_number, numbers, learning_rate, batch_size, N_epochs, seed):
    wandb.init(
        project="probabilistic-arithmetic",
        name=f"addition_{digits_per_number}_{numbers}_{seed}",
        config={
            "digits": digits_per_number,
            "numbers": numbers,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "epochs": N_epochs,
            "seed": seed,
        },
    )

    model = SumClassifier()

    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    loss_object = tf.keras.losses.SparseCategoricalCrossentropy(from_logits=True)

    train_data, val_data, test_data = create_loader(digits_per_number, numbers)

    trainer = Trainer(
        model,
        optimizer,
        loss_object,
        train_data,
        val_data,
        sum_accuracy,
        epochs=N_epochs,
    )
    trainer.train()

    test_accuracy = sum_accuracy(model, test_data)
    wandb.log({"test_accuracy": test_accuracy.numpy()})

    print(f"Test accuracy: {test_accuracy.numpy()}")
    wandb.finish()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--digits_per_number", default=6, type=int)
    parser.add_argument("--numbers", default=2, type=int)
    parser.add_argument("--learning_rate", default=1e-3, type=float)
    parser.add_argument("--batch_size", default=10, type=int)
    parser.add_argument("--N_epochs", default=20, type=int)
    parser.add_argument("--N_runs", default=10, type=int)

    args = parser.parse_args()

    for seed in range(args.N_runs):
        p = mp.Process(
            target=train,
            args=(
                args.digits_per_number,
                args.numbers,
                args.learning_rate,
                args.batch_size,
                args.N_epochs,
                seed,
            ),
        )
        p.start()
        p.join()
