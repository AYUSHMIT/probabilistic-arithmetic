import time
import wandb
import tensorflow as tf


class Trainer:

    def __init__(
        self,
        model,
        optimizer,
        loss_object,
        train_dataset,
        val_dataset,
        val_fn,
        encoding,
        epochs=10,
        log_its=100,
    ):
        self.model = model
        self.optimizer = optimizer
        self.loss_object = loss_object
        self.train_dataset = train_dataset
        self.val_dataset = val_dataset
        self.val_fn = val_fn
        self.encoding = encoding
        self.epochs = epochs
        self.log_its = log_its

    @tf.function
    def train_step(self, images, label):
        with tf.GradientTape() as tape:
            loss = 0
            predictions = self.model(images)
            if self.encoding == "sum":
                loss += self.loss_object(label, predictions.logits)
            elif self.encoding == "carry":
                predictions = tf.stack([pred.logits for pred in predictions], axis=-2)
                label = tf.expand_dims(label, axis=-1)
                loss += self.loss_object(label, predictions)

        gradients = tape.gradient(loss, self.model.trainable_variables)
        self.optimizer.apply_gradients(zip(gradients, self.model.trainable_variables))
        return loss

    def train(self):
        avg_loss = tf.keras.metrics.Mean()
        duration = tf.keras.metrics.Sum()
        count = 0
        for epoch in range(self.epochs):
            for data in self.train_dataset:
                images = data[0]
                labels = data[1]

                start_time = time.time()
                loss = self.train_step(images, labels)
                training_time = time.time() - start_time

                avg_loss.update_state(loss)
                duration.update_state(training_time)
                if count % self.log_its == 0:
                    acc = self.val_fn(self.model, self.val_dataset)

                    print_text = [f"Epoch {epoch + 1}"]
                    print_text += [f"\tIteration: {count}"]
                    print_text += [f"\tLoss: {avg_loss.result().numpy()}"]
                    print_text += [f"\tVal Accuracy: {acc.numpy()}"]
                    print_text += [f"\tTime(s): {duration.result().numpy()}"]

                    print(*print_text)

                    wandb.log(
                        {
                            "loss": avg_loss.result().numpy(),
                            "accuracy": acc.numpy(),
                            "time": duration.result().numpy(),
                        }
                    )
                    avg_loss.reset_states()
                    duration.reset_states()
                count += 1
