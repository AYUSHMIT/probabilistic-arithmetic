import os
import sys
import multiprocessing as mp
import argparse
from pathlib import Path

import tensorflow as tf
import wandb


PARENT_DIR = Path(__file__).resolve().parent
sys.path.append(str(PARENT_DIR / "../.."))

from classifier import LuhnClassifier
from data.generation import create_loader
from trainer import Trainer


os.environ["TF_FORCE_GPU_ALLOW_GROWTH"] = "true"


def accuracy(model, data):
    correct = 0
    total = 0
    for batch in data:
        identifier, label = batch
        prediction = model(identifier)
        prediction = tf.argmax(prediction.logits, axis=-1)
        correct += tf.reduce_sum(tf.cast(prediction == label, tf.int32))
        total += tf.size(label)
    return correct / total


def train(id_length, learning_rate, batch_size, N_epochs, seed):
    wandb.init(
        project="probabilistic-arithmetic",
        name=f"luhn_{id_length}_{seed}",
        config={
            "id_length": id_length,
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "N_epochs": N_epochs,
            "seed": seed,
        },
    )

    model = LuhnClassifier()

    optimizer = tf.keras.optimizers.Adam(learning_rate=learning_rate)
    loss_object = tf.keras.losses.BinaryCrossentropy(from_logits=True)

    train_data, val_data, test_data = create_loader(batch_size, id_length)

    trainer = Trainer(
        model,
        optimizer,
        loss_object,
        train_data,
        val_data,
        accuracy,
        epochs=N_epochs,
    )
    trainer.train()

    test_accuracy = accuracy(model, test_data)
    wandb.log({"test_accuracy": test_accuracy.numpy()})
    print(f"Test accuracy: {test_accuracy.numpy()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--id_length", type=int)
    parser.add_argument("--learning_rate", default=1e-3, type=float)
    parser.add_argument("--batch_size", type=int)
    parser.add_argument("--N_epochs", type=int)
    parser.add_argument("--N_runs", type=int)

    args = parser.parse_args()

    for seed in range(args.N_runs):
        p = mp.Process(
            target=train,
            args=(
                args.id_length,
                args.learning_rate,
                args.batch_size,
                args.N_epochs,
                seed,
            ),
        )
        p.start()
        p.join()
