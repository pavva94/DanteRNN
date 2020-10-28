# -*- coding: utf-8 -*-
"""RNN_text_generator_00.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/10lc5d3SR-hwAyQA81gtT3p-RzUSXKWi0

# TensorFlow 2 Text generator on Dante Alighieri's Divine Comedy

Author: **Ivan Bongiorni**, [LinkedIn profile](https://www.linkedin.com/in/ivan-bongiorni-b8a583164/)

This Notebook contains a **text generator RNN** that was trained on the **Divina Commedia** (the *Divine Comedy*) by **Dante Alighieri**. This is a poem written at the beginning of the XII century. It's hard to explain what it represents for Italian culture: it's without any doubt the main pillar of our national literature, one of the building blocks of modern Italian language, and arguably the gratest poem ever. All modern representations of Hell, Purgatory and Heaven derive from this opera.

It's structure is extremely interesting: each verse is composed of 11 syllables, and its rhymes follow an **A-B-A-B** structure. Lot of pattern to be learned!
"""

# Commented out IPython magic to ensure Python compatibility.
import time
import re

import numpy as np
import pandas as pd

# %tensorflow_version 2.x
import tensorflow as tf
print(tf.__version__)

from matplotlib import pyplot as plt

# Read file from Colab Notebook
#from google.colab import drive
#drive.mount('/content/drive')

current_path = " [...] /TF_2.0/NLP/text_generator/"

# Read the Divina Commedia
with open( "DivinaCommedia.txt", 'r', encoding="utf8") as file:
    divina_commedia = file.read()

# Replace rare characters
divina_commedia = divina_commedia.replace("ä", "a")
divina_commedia = divina_commedia.replace("é", "è")
divina_commedia = divina_commedia.replace("ë", "è")
divina_commedia = divina_commedia.replace("Ë", "E")
divina_commedia = divina_commedia.replace("ï", "i")
divina_commedia = divina_commedia.replace("Ï", "I")
divina_commedia = divina_commedia.replace("ó", "ò")
divina_commedia = divina_commedia.replace("ö", "o")
divina_commedia = divina_commedia.replace("ü", "u")

divina_commedia = divina_commedia.replace("(", "-")
divina_commedia = divina_commedia.replace(")", "-")
#divina_commedia = divina_commedia.replace("[", "")
#divina_commedia = divina_commedia.replace("]", "")

divina_commedia = re.sub(r'[0-9]+', '', divina_commedia)
divina_commedia = re.sub(r'\[.*\r?\n', '', divina_commedia)
divina_commedia = re.sub(r'.*Canto.*\r?\n', '', divina_commedia)

# divina_commedia = divina_commedia.replace(" \n", "\n")  # with this i lose the "terzina": results are not so exciting
#divina_commedia = divina_commedia.replace(" \n", "<eot>")  # end of terzina
#divina_commedia = divina_commedia.replace("\n", "<eor>")

print(divina_commedia[1:1000])

# Check lenght of text
print(len(divina_commedia))

"""I will now extract the set of unique characters, and create a dictionary for vectorization of text. In order to feed the text into a Neural Network, I must turn each character into a number."""

# Store unique characters into a dict with numerical encoding
unique_chars = list(set(divina_commedia))
unique_chars.sort()  # to make sure you get the same encoding at each run

# Store them in a dict, associated with a numerical index
char2idx = { char[1]: char[0] for char in enumerate(unique_chars) }

print(len(char2idx))

char2idx

"""Once I have a dictionary that maps each characted with its respective numerical index, I can process the whole corpus."""

def numerical_encoding(text, char_dict):
    """ Text to list of chars, to np.array of numerical idx """
    chars_list = [ char for char in text ]
    chars_list = [ char_dict[char] for char in chars_list ]
    chars_list = np.array(chars_list)
    return chars_list

# Let's see what the first line will look like
print("{}".format(divina_commedia[276:511]))
print("\nbecomes:")
print(numerical_encoding(divina_commedia[276:511], char2idx))

"""## RNN dataprep

I need to generate a set of stacked input sequences. My goal is to train a Neural Network to find a mapping between an input sequence and an output sequence of equal length, in which each character is shifted left of one position.

For example, the first verse:

> Nel mezzo del cammin di nostra vita

would be translated in a train sequence as:

`Nel mezzo del cammin di nostra vit`

be associated with the target sequence:

`el mezzo del cammin di nostra vita`

The following function is a preparatory step for that. More generally, given a sequence:

```
A B C D E F G H I
```

and assuming input sequences of length 5, it will generate a matrix like:

```
A B C D E
B C D E F
C D E F G
D E F G H
E F G H I
```

I will save that matrix as it is in .csv format, to use it to train the Language Generator later.
The split between train and target sets will be as:

```
 Train:           Target:
                 
A B C D E        B C D E F
B C D E F        C D E F G
C D E F G        D E F G H
D E F G H        E F G H I
                 
```

Train and target sets are fundamentally the same matrix, with the train having the last row removed, and the target set having the first removed.
"""

# Apply it on the whole Comedy
encoded_text = numerical_encoding(divina_commedia, char2idx)

print(encoded_text[311:600])

def get_text_matrix(sequence, len_input):
    
    # create empty matrix
    X = np.empty((len(sequence)-len_input, len_input))
    
    # fill each row/time window from input sequence
    for i in range(X.shape[0]):
        X[i,:] = sequence[i : i+len_input]
        
    return X

text_matrix = get_text_matrix(encoded_text, 200)

print(text_matrix.shape)

print("100th train sequence:\n")
print(text_matrix[ 100, : ])
print("\n\n100th target sequence:\n")
print(text_matrix[ 101, : ])
print("\n\n102th target sequence:\n")
print(text_matrix[ 102, : ])
print("\n\n115th target sequence:\n")
print(text_matrix[ 180, : ])

"""# Architecture

At this point, I can specify the RNN architecture with all its hyperparameters. An `Embedding()` layer will first learn a representation of each character; the sequence of chracters embedding will then be fed into an `LSTM()` layer, that will extract information from their sequence; `Dense()` layers at the end will produce the next character prediction.

The Network is structured to be fed with batches of data of fixed size.
"""

# size of vocabulary
vocab_size = len(char2idx)

# size of mini batches during training
batch_size = 200  # 100


# size of training subset at each epoch
subset_size = batch_size * 100

# vector size of char embeddings
embedding_size = 300  # 250

len_input = 1024   # 200

hidden_size = 300  # for Dense() layers 250

from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout
from tensorflow.keras.activations import elu, relu, softmax

'''
EXPERIMENT
CUSTOM LOSS
'''
def divide_versi(y):
  doppiozero = False

  # per forza devo avere 4 versi, si può????
  y_divided = [[]]
  for ly in y:
    ly = int(ly)

    if ly is 0:
      if not doppiozero:
        y_divided.append([])
      doppiozero = True
      continue

    y_divided[-1].append(ly)
    doppiozero = False

  if y[-1] != 0:
    # dato che l'ultima riga non finisce con 0 vuol dire che è incompleta e la rimuovo
    y_divided.pop()

  if len(y_divided[0]) < 4:
    # se la prima riga è minore di 4 non posso farci nulla quindi la elimino
    y_divided.pop(0)

  return y_divided

def rhymes_extractor(y_divided):
  # estraggo lo schema di rime da y
  rhymes = []
  for i in range(len(y_divided)):
    # con la fine del verso (ultime due lettere) controllo se le altre righe 
    # finiscono con le stesse lettere
    vy = y_divided[i]

    # ABA BCB CDC

    # devo controllare se la riga i fa rima con la riga i+2 
    if i+2 < len(y_divided):
      next_vy = y_divided[i+2]
      if vy[-2:-1] == next_vy[-2:-1]:
        rhymes.append((i, i+2))
    if i+4 < len(y_divided):
      next_vy = y_divided[i+4]
      if vy[-2:-1] == next_vy[-2:-1]:
        rhymes.append((i, i+4))

  # print(rhymes)
  return rhymes


def get_custom_loss(x_batch, y_batch):

  summed_custom_loss = 0
  for (x, y) in zip(x_batch, y_batch):
    x_divided = divide_versi(x)
    y_divided = divide_versi(y)
    # print(y_divided)

    # assert len(x_divided) == len(y_divided)

    x_rhymes = rhymes_extractor(x_divided)
    y_rhymes = rhymes_extractor(y_divided)

    if x_rhymes == y_rhymes:
      custom_loss = -0.2
      return custom_loss

    custom_loss = 0.
    if len(x_rhymes) == len(y_rhymes):
      for i in range(len(x_rhymes)):
        if x_rhymes[i] not in y_rhymes:
          custom_loss += 0.15

    summed_custom_loss += custom_loss
      
  print(summed_custom_loss/x_batch.shape[0])
  return summed_custom_loss/x_batch.shape[0]

'''
EXPERIMENT
MODEL
'''
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Embedding, LSTM, Dense, Dropout, Attention, Flatten, Input
from tensorflow.keras.activations import elu, relu, softmax
from tensorflow.keras.metrics import categorical_accuracy, sparse_categorical_crossentropy, categorical_crossentropy
# Define custom training utilities that are widely used for language modelling

n_epochs = 100

learning_rate = 0.001  # 0.0001
optimizer = tf.keras.optimizers.Adamax(learning_rate=learning_rate)  # Adam

def loss(y_true, y_pred):
    """Calculates categorical crossentropy as loss"""
    return categorical_crossentropy(y_true=y_true, y_pred=y_pred)


def perplexity(labels, logits):
    """Calculates perplexity metric = 2^(entropy) or e^(entropy)"""
    return pow(2, loss(y_true=labels, y_pred=logits))

# Input Layer
X = Input(shape=(None, ), batch_size=batch_size)  # 100 is the number of features

# Word-Embedding Layer
embedded = Embedding(vocab_size, embedding_size, batch_input_shape=(batch_size, None))(X)
embedded = Dense(embedding_size, relu)(embedded)
encoder_output, hidden_state, cell_state = LSTM(units=512,
                                                         return_sequences=True,
                                                         return_state=True)(embedded)
#attention_input = [encoder_output, hidden_state]
encoder_output = Dropout(0.3)(encoder_output)
encoder_output = Dense(embedding_size, activation='relu')(encoder_output)

#encoder_output = Attention()(attention_input, training=True)

initial_state = [hidden_state,  cell_state]

initial_state_double = [tf.concat([hidden_state, hidden_state], 1), tf.concat([hidden_state, hidden_state], 1)]
encoder_output, hidden_state, cell_state = LSTM(units=1024,
                                                         return_sequences=True,
                                                         return_state=True)(encoder_output, initial_state=initial_state_double)
encoder_output = Dropout(0.3)(encoder_output)
#encoder_output = Flatten()(encoder_output)
encoder_output = Dense(hidden_size, activation='relu')(encoder_output)
# Prediction Layer
Y = Dense(units=vocab_size)(encoder_output)

# Compile model
model = Model(inputs=X, outputs=Y)
model.compile(loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True), optimizer='adam', metrics=[perplexity, sparse_categorical_crossentropy])
print(model.summary())

# This is an Autograph function
# its decorator makes it a TF op - i.e. much faster
# @tf.function
def train_on_batch(x, y):
    
    with tf.GradientTape() as tape:
        current_loss = tf.reduce_mean(
            tf.keras.losses.sparse_categorical_crossentropy(
                y, model(x), from_logits = True)
            + get_custom_loss(x, y)
            )
    gradients = tape.gradient(current_loss, model.trainable_variables)
    optimizer.apply_gradients(zip(gradients, model.trainable_variables))
    return current_loss


loss_history = []

for epoch in range(n_epochs):
    start = time.time()
    
    # Take subsets of train and target
    sample = np.random.randint(0, text_matrix.shape[0]-1, subset_size)
    sample_train = text_matrix[ sample , : ]
    sample_target = text_matrix[ sample+1 , : ]


    #sample = list(range(subset_size*epoch, subset_size*(epoch+1)))
    #sample_train = text_matrix[ sample , : ]
    #next_sample = [x+1 for x in sample]
    #sample_target = text_matrix[ next_sample , : ]
    
    for iteration in range(sample_train.shape[0] // batch_size):
        take = iteration * batch_size
        x = sample_train[ take:take+batch_size , : ]
        y = sample_target[ take:take+batch_size , : ]

        current_loss = train_on_batch(x, y)
        loss_history.append(current_loss)
    
    print("{}.  \t  Loss: {}  \t  Time: {}sec/epoch".format(
        epoch+1, current_loss.numpy(), round(time.time()-start, 2)))

model.save("model_piramid_02.h5")

'''
EXPERIMENT
GENERATOR
'''

# Input Layer
X = Input(shape=(None, ), batch_size=1)  # 100 is the number of features

# Word-Embedding Layer
embedded = Embedding(vocab_size, embedding_size, batch_input_shape=(batch_size, None))(X)
embedded = Dense(embedding_size, relu)(embedded)
encoder_output, hidden_state, cell_state = LSTM(units=512,
                                                         return_sequences=True,
                                                         return_state=True,
                                                stateful=True)(embedded)
#attention_input = [encoder_output, hidden_state]

encoder_output = Dropout(0.3)(encoder_output)

encoder_output = Dense(embedding_size, activation='relu')(encoder_output)

#encoder_output = Attention()(attention_input, training=True)
initial_state = [hidden_state,  cell_state]

initial_state_double = [tf.concat([hidden_state, hidden_state], 1), tf.concat([hidden_state, hidden_state], 1)]
encoder_output, hidden_state, cell_state = LSTM(units=1024,
                                                         return_sequences=True,
                                                         return_state=True,
                                                stateful=True)(encoder_output, initial_state=initial_state_double)
#encoder_output = Flatten()(encoder_output)
encoder_output = Dropout(0.3)(encoder_output)
encoder_output = Dense(hidden_size, activation='relu')(encoder_output)
# Prediction Layer
Y = Dense(units=vocab_size)(encoder_output)

# Compile model
generator = Model(inputs=X, outputs=Y)
generator.compile(loss=tf.keras.losses.SparseCategoricalCrossentropy(from_logits = True), optimizer='adam', metrics=[perplexity, sparse_categorical_crossentropy])
print(model.summary())


# Import trained weights from model to generator
generator.set_weights(model.get_weights())

def generate_text(start_string, num_generate = 1000, temperature = 1.0):
    
    # Vectorize input string
    input_eval = [char2idx[s] for s in start_string]  
    input_eval = tf.expand_dims(input_eval, 0)
    
    text_generated = [] # List to append predicted chars 
    
    idx2char = { v: k for k, v in char2idx.items() }  # invert char-index mapping
    
    generator.reset_states()
    
    for i in range(num_generate):
        predictions = generator(input_eval)
        predictions = tf.squeeze(predictions, 0)
        
        # sample next char based on distribution and temperature
        predictions = predictions / temperature
        predicted_id = tf.random.categorical(predictions, num_samples=1)[-1,0].numpy()
        
        input_eval = tf.expand_dims([predicted_id], 0)

        text_generated.append(idx2char[predicted_id])
        
    return (start_string + ''.join(text_generated))


# Let's feed the first lines:
start_string = """
Nel mezzo del cammin di nostra vita
mi ritrovai per una selva oscura,
chè la diritta via era smarrita.

"""

for t in [0.1, 0.5, 1.0, 1.5, 2]:
    print("####### TEXT GENERATION - temperature = {}\n".format(t))
    print(generate_text(start_string = start_string, num_generate = 1000, temperature = t))
    print("\n\n\n")

RNN = Sequential([
    Embedding(vocab_size, embedding_size,
              batch_input_shape=(batch_size, None)),
    Dense(embedding_size, activation = relu),
    
    LSTM(len_input, return_sequences = True),

    Dropout(0.33),
    
    Dense(hidden_size, activation = relu), 

    Dropout(0.33),

    LSTM(len_input, return_sequences = True),
    
    Dense(vocab_size)
])

RNN.summary()

n_epochs = 20

learning_rate = 0.001  # 0.0001
optimizer = tf.keras.optimizers.Adamax(learning_rate = learning_rate)  # Adam

# This is an Autograph function
# its decorator makes it a TF op - i.e. much faster
@tf.function
def train_on_batch(x, y):
    with  tf.GradientTape() as tape:
        # TODO: implementare la custom loss prendendo le rime da Y 
        # e controllando che schema di rime c'è
        # Avendo lo schema di rime controllare la X e dare un voto sugli ultimi
        # 3 caratteri. Dando un punteggio coerente con il numero di lettere 
        # che fanno rima, valutare un punteggio negativo

        current_loss = tf.reduce_mean(
            tf.keras.losses.sparse_categorical_crossentropy(
                y, RNN(x), from_logits = True))
    gradients = tape.gradient(current_loss, RNN.trainable_variables)
    optimizer.apply_gradients(zip(gradients, RNN.trainable_variables))
    return current_loss

loss_history = []

for epoch in range(n_epochs):
    start = time.time()
    
    # Take subsets of train and target
    #sample = list(range(r1, r2+1))
    #sample = np.random.randint(0, text_matrix.shape[0]-1, subset_size)
    #sample_train = text_matrix[ sample , : ]
    #sample_target = text_matrix[ sample+1 , : ]

    # NEW SEQUENTIAL MODE
    sample = list(range(subset_size*epoch, subset_size*(epoch+1)))
    sample_train = text_matrix[ sample , : ]
    next_sample = [x+1 for x in sample]
    sample_target = text_matrix[ next_sample , : ]
    
    for iteration in range(sample_train.shape[0] // batch_size):
        take = iteration * batch_size
        x = sample_train[ take:take+batch_size , : ]
        y = sample_target[ take:take+batch_size , : ]

        current_loss = train_on_batch(x, y)
        loss_history.append(current_loss)
    
    print("{}.  \t  Loss: {}  \t  Time: {}ss".format(
        epoch+1, current_loss.numpy(), round(time.time()-start, 2)))

plt.plot(loss_history)
plt.title("Training Loss")
plt.show()

RNN.save( "text_generator_RNN_03.h5")

"""# Text Generation

At this point, let's check how the model generates text. In order to do it, I must make some changes to my RNN architecture above.

First, I must change the fixed batch size. After training, I want to feed just one sentence into my Network to make it continue the character sequence. I will feed a string into the model, make it predict the next character, update the input sequence, and repeat the process until a long generated text is obtained. Because of this, the succession of input sequences is now different from training session, in which portions of text were sampled randomly. I now have to set `stateufl = True` in the `LSTM()` layer, so that each LSTM cell will keep in memory the internal state from the previous sequence. With this I hope the model will better remember sequential information while generating text.

I will instantiate a new `generator` RNN with these new features, and transfer the trained weights of my `RNN` into it.
"""

generator = Sequential([
   Embedding(vocab_size, embedding_size,
              batch_input_shape=(1, None)),
    Dense(embedding_size, activation = relu),
    
    LSTM(len_input, return_sequences = True, stateful=1),

    Dropout(0.3),
    
    Dense(hidden_size, activation = relu), 

    Dropout(0.3),

    LSTM(len_input, return_sequences = True, stateful=1),
    
    Dense(vocab_size)
])

generator.summary()

# Import trained weights from RNN to generator
generator.set_weights(RNN.get_weights())

def generate_text(start_string, num_generate = 1000, temperature = 1.0):
    
    # Vectorize input string
    input_eval = [char2idx[s] for s in start_string]  
    input_eval = tf.expand_dims(input_eval, 0)
    
    text_generated = [] # List to append predicted chars 
    
    idx2char = { v: k for k, v in char2idx.items() }  # invert char-index mapping
    
    generator.reset_states()
    
    for i in range(num_generate):
        predictions = generator(input_eval)
        predictions = tf.squeeze(predictions, 0)
        
        # sample next char based on distribution and temperature
        predictions = predictions / temperature
        predicted_id = tf.random.categorical(predictions, num_samples=1)[-1,0].numpy()
        
        input_eval = tf.expand_dims([predicted_id], 0)

        text_generated.append(idx2char[predicted_id])
        
    return (start_string + ''.join(text_generated))

"""(This function is based on [this tutorial](https://www.tensorflow.org/tutorials/text/text_generation).)"""

# Let's feed the first lines:
start_string = """
Nel mezzo del cammin di nostra vita
mi ritrovai per una selva oscura,
chè la diritta via era smarrita.

"""

for t in [0.1, 0.5, 1.0, 1.5, 2]:
    print("####### TEXT GENERATION - temperature = {}\n".format(t))
    print(generate_text(start_string = start_string, num_generate = 1000, temperature = 1.0))
    print("\n\n\n")

"""The best generation is, IMHO, the one with `temperature = 1.5`. The sentences of course do not make sense, but it's amazing that such a simple model could achieve similar results, and generate absolutely Dante-esque text with just ~40 minutes of GPU training.

Many things could be done at this point:



*   Try fancier architectures, such as seq2seq. (I must say though that stacked RNNs didn't provide better results during prototyping.)
*   Try Attention models.
*   Longer training.
*   Adversarial training.

I'll try a lot of these techniques, alone and combined. My goal is to make a model that can learn the amazing structure of syllables and rhymes of the whole Comedy.

# NEW IDEAS

#### Training:
*   Cross validation
*   Insert Rhyme as feature to learn as haiku
*   Use syllable as input and not word
*   Different training on different dataset
* Use categorical_crossentropy instead of sparse_ but with one-hot encoded inputs
* Symbols for explicit start and end terzina
* training as classificator for structure: like "these two world are rhymes" or "this is a endecasillable and this not" or "this is a terzina and this not" then generation
* use dropout 
* use two lstm
* 

#### Presentation
* graphs over the vocabulary like distribution of used words
"""

RNN = Sequential([
    Embedding(vocab_size, embedding_size,
              batch_input_shape=(batch_size, None)),
              
    Dense(embedding_size, activation = relu),
    
    LSTM(len_input, return_sequences = True),

    Dropout(0.3),
    
    Dense(hidden_size, activation = relu), 

    Dropout(0.3),
    
    Dense(vocab_size)
])

RNN.summary()

generator = Sequential([
    Embedding(vocab_size, embedding_size,batch_input_shape=(1, None)),

    Dense(embedding_size, activation = relu),
    
    LSTM(len_input, return_sequences = True, stateful=True),

    Dropout(0.3),
    
    Dense(hidden_size, activation = relu), 

    Dropout(0.3),
    
    Dense(vocab_size)


])

generator.summary()