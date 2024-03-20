import tensorflow as tf
import numpy as np
import einops as E

from plia import Krat, log_expectation, log1mexp


class ViSudoClassifier(tf.keras.Model):

    def __init__(self, grid_size: int = 9):
        super().__init__()
        self.digit_classifier = ViSudoDigitClassifier(grid_size)
        self.sudoku_solver = SudokuSolver(grid_size)

    def call(self, inputs, training=None, mask=None):
        x = self.digit_classifier(inputs)
        x = self.sudoku_solver(x)
        x = tf.reduce_sum(x, axis=-1)
        return x


# class SudokuSolver(tf.keras.Model):

#     def __init__(self, grid_size):
#         super().__init__()
#         self.grid_size = grid_size

#     def binary_representation(self, inputs, grid_size):
#         rows = []
#         for i in range(grid_size):
#             column = []
#             for j in range(grid_size):
#                 binaries = []
#                 for k in range(grid_size):
#                     logit_k = inputs[:, i, j, k]
#                     binary = PInt(tf.stack([-logit_k, logit_k], -1), 0)
#                     binaries.append(binary)
#                 column.append(binaries)
#             rows.append(column)
#         return rows

#     def binary_numpy_representation(self, inputs, grid_size):
#         representation = self.binary_representation(inputs, grid_size)
#         representation = np.array(representation, dtype=object)
#         return representation

#     def distinct_row_elements(self, inputs):
#         x = E.reduce(inputs, "row column binaries -> (row binaries)", "sum")
#         row_constraints = [0] * len(x)
#         for i, _ in enumerate(x):
#             row_constraints[i] = log_expectation(x[i] == 1)
#         row_constraints = tf.stack(row_constraints, axis=1)
#         return row_constraints

#     def distinct_column_elements(self, inputs):
#         x = E.reduce(inputs, "row column binaries -> (column binaries)", "sum")
#         column_constraints = [0] * len(x)
#         for j, _ in enumerate(x):
#             column_constraints[j] = log_expectation(x[j] == 1)
#         column_constraints = tf.stack(column_constraints, axis=1)
#         return column_constraints

#     def distinct_box_elements(self, inputs):
#         row = inputs.shape[0]
#         column = inputs.shape[1]
#         binaries = inputs.shape[2]
#         box_row = row // 3
#         box_column = column // 3
#         x = E.rearrange(
#             inputs,
#             "(box_row r) (box_column c) binaries -> box_row box_column (r c) binaries",
#             r=3,
#             c=3,
#             box_row=box_row,
#             box_column=box_column,
#         )
#         x = E.reduce(
#             x,
#             "box_row box_column box binaries -> (box_row box_column binaries)",
#             "sum",
#         )

#         box_constraints = [0] * len(x)
#         for i, _ in enumerate(x):
#             box_constraints[i] = log_expectation(x[i] == 1)
#         box_constraints = tf.stack(box_constraints, axis=1)
#         return box_constraints

#     def call(self, inputs, training=None, mask=None):
#         grid_size = inputs.shape[-1]

#         x = self.binary_numpy_representation(inputs, grid_size)
#         row_constraint = self.distinct_row_elements(x)
#         column_constraint = self.distinct_column_elements(x)

#         if grid_size == 9:
#             box_constraint = self.distinct_box_elements(x)
#             return tf.concat(
#                 [row_constraint, column_constraint, box_constraint], axis=-1
#             )
#         else:
#             return tf.concat([row_constraint, column_constraint], axis=-1)


class SudokuSolver(tf.keras.Model):

    def __init__(self, grid_size):
        super().__init__()
        self.grid_size = grid_size

    def binarize(self, probs):
        # neg_probs = log1mexp(probs)
        neg_probs = -probs
        return tf.stack([neg_probs, probs], -1)
        # return E.rearrange([neg_probs, probs], "2 ... -> ... 2")

    def distinct_row_elements(self, inputs):
        return E.rearrange(inputs, "b r c p 2 -> b c r p 2")

    def distinct_column_elements(self, inputs):
        return E.rearrange(inputs, "b r c p 2 -> b c r p 2")

    def distinct_box_elements(self, inputs):
        box_dim = int(np.sqrt(self.grid_size))
        return E.rearrange(
            inputs,
            "b (r box_r) (c box_c) p -> b (r c) (box_r box_c) p",
            r=box_dim,
            c=box_dim,
        )

    def get_constraints(self, x, ctype):
        if ctype == "row":
            return E.rearrange(x, "b r c p binaries -> b (r p) c binaries")
        elif ctype == "column":
            return E.rearrange(x, "b r c p binaries -> b (c p) r binaries")
        elif ctype == "box":
            box_dim = int(np.sqrt(self.grid_size))
            return E.rearrange(
                x,
                "b (r box_r) (c box_c) p binaries -> b (r c p) (box_r box_c) binaries",
                r=box_dim,
                c=box_dim,
            )
        else:
            raise NotImplementedError()

    def call(self, inputs, training=None, mask=None):
        x = self.binarize(inputs)
        constraints = []

        constraints.append(self.get_constraints(x, "row"))
        constraints.append(self.get_constraints(x, "column"))
        if self.grid_size == 9:
            constraints.append(self.get_constraints(x, "box"))
        constraints = E.rearrange(
            constraints,
            "i b constraint_index constraints binaries -> b (constraint_index i) constraints binaries",
        )

        krat_constraints = Krat(constraints, 0)
        pintjes = krat_constraints.sum_reduce()
        expectation = log_expectation(pintjes == 1)
        return expectation


class ViSudoDigitClassifier(tf.keras.Model):

    def __init__(self, grid_size: int = 9):
        self.grid_size = grid_size
        super(ViSudoDigitClassifier, self).__init__()

        self.model = tf.keras.Sequential()
        self.model.add(tf.keras.layers.Conv2D(6, 5, activation="relu"))
        self.model.add(tf.keras.layers.MaxPooling2D())
        self.model.add(tf.keras.layers.Conv2D(16, 5, activation="relu"))
        self.model.add(tf.keras.layers.MaxPooling2D())
        self.model.add(tf.keras.layers.Flatten())
        self.model.add(tf.keras.layers.Dense(120, activation="relu"))
        self.model.add(tf.keras.layers.Dense(84, activation="relu"))
        self.model.add(tf.keras.layers.Dense(grid_size))

    def call(self, inputs, training=None, mask=None):
        inputs = E.rearrange(inputs, "b row column ... -> (b row column) ...")
        inputs = tf.expand_dims(inputs, axis=-1)
        x = self.model(inputs)
        x = E.rearrange(
            x,
            "(b row column) ... -> b row column ...",
            row=self.grid_size,
            column=self.grid_size,
        )
        return x
