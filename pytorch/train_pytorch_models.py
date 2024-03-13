import sys
import os
import time 

from datetime import datetime
from models import valid_models, LSTMFCN

import numpy as np
import torch
import onnx
from onnxsim import simplify

from dataloader import get_Dataloaders
sys.path.append("../utils")
from util import models_dir, result_dir, archiv_dir, get_all_datasets, create_results_csv, add_results 

def get_lr(optimizer):
    for param_group in optimizer.param_groups:
        return param_group['lr']

def train_model(model_id, model_name, device, dataset, hidden_size, n_layers, positional_encoding, simplify, 
                     n_epochs=2000, batch_size=128, learning_rate=0.001): 
    
    dl_train, dl_test, metrics = get_Dataloaders(dataset, batch_size, positional_encoding)
    seq_len, input_dim, n_classes = metrics

    _, gen_model = valid_models[model_id]

    filters = [128, 256, 128]
    kernels = [3, 5, 8]

    model = LSTMFCN(device, input_dim, hidden_size, n_classes, n_layers, filters, kernels)
    model.to(device)

    checkpoint_path = os.path.join("./checkpoints", model_name)

    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
        optimizer,
        mode="min",
        factor=1. / np.cbrt(2),
        patience=100,
        min_lr=1e-4
    )
    criterion = torch.nn.CrossEntropyLoss()

    start_time = time.time()
    best_val_acc = 0

    for e in range(n_epochs):
        model.train()
        for x_batch, y_batch in dl_train:
            x_batch = torch.permute(x_batch, (1, 0, 2)).to(device)
            y_batch = y_batch.to(device)

            out = model(x_batch)
            loss = criterion(out, y_batch)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
        scheduler.step(loss)

        # eval model
        with torch.no_grad():
            model.eval()
            correct = 0
            total = 0
            
            for x_batch, y_batch in dl_test:
                x_batch = torch.permute(x_batch, (1, 0, 2)).to(device)
                y_batch = y_batch.to(device)
                
                out = model(x_batch)
                _, pred = torch.max(out,1)
                correct += (pred == y_batch).sum().item()
                total += len(y_batch)

            acc = correct / total            

            if e % 10 == 0:
                print("Epoch:", e, "train_loss:", loss.item(), "val_acc:", acc, "lr:", get_lr(optimizer), "\n")
            
            if acc > best_val_acc:
                best_val_acc = acc 
                torch.save(model, checkpoint_path)

    train_time = time.time() - start_time
    
    export_model(checkpoint_path, model_name, dataset, seq_len, input_dim, device)

    return train_time

def test_model(model_name, device, dataset, positional_encoding, batch_size=128):
    _, dl_test, _ = get_Dataloaders(dataset, batch_size, positional_encoding)
    
    model = torch.load(os.path.join("checkpoints", model_name))

    model.eval()
    correct = 0
    total = 0
    
    for x_batch, y_batch in dl_test:
        x_batch = torch.permute(x_batch, (1, 0, 2)).to(device)
        y_batch = y_batch.to(device)
        
        out = model(x_batch)
        _, pred = torch.max(out,1)
        correct += (pred == y_batch).sum().item()
        total += len(y_batch)

    acc = correct / total            
    return acc, 0, 0

def simplify_model(model_file):

    onnx_model = onnx.load(model_file)
    onnx_simplified, _ = simplify(onnx_model)

    graph = onnx_simplified.graph
    for node in graph.node:
        if node.op_type == "LSTM":
            # remove state outputs
            del node.output[1]
            del node.output[1]

    onnx.save(onnx_simplified, model_file)

def export_model(model_checkpoint, model_name, dataset, seq_len, input_dim, device):
    
    model = torch.load(model_checkpoint)
    # export model to .onnx
    dummy_input = torch.randn(seq_len, 1, input_dim).to(device)

    model_file = os.path.join(models_dir, model_name + "_" + dataset + ".onnx")
    onnx_model = torch.onnx.export(model, 
                                     dummy_input, 
                                     model_file,
                                     export_params=True,
                                     input_names =  ["input"],
                                     output_names =  ["output"])

    if simplify and model_name == "vanilla_lstm":
        simplify_model(model_file)

def train_eval_loop(model_id, hidden_size, n_layers, simplify, positional_encoding=False):

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # datasets = get_all_datasets()
    datasets = os.listdir(archiv_dir)

    model_name, _ = valid_models[model_id] 

    if positional_encoding:
        model_name += "_posenc"

    time_stamp = datetime.now().strftime("%m_%d_%Y_%H:%M:%S") 
    result_file = os.path.join(result_dir, "pytorch_" + model_name + "_results_" + time_stamp + ".csv")

    create_results_csv(result_file)

    for ds in sorted(datasets):
        print("Training: %s %s" % (model_name, ds))
        train_time = train_model(model_id, model_name, device, ds, hidden_size, n_layers, positional_encoding, simplify) 
        acc, prec, recall = test_model(model_name, device, ds, positional_encoding)

        add_results(result_file, ds, acc, prec, recall, train_time)


if __name__ == "__main__":

    hidden_size = [128]
    n_layers = 1    
    for hs in hidden_size:
        train_eval_loop(2, hs, n_layers, simplify=False, positional_encoding=True)
    # for model_id in range(len(valid_models)):
    #     train_eval_loop(model_id, hidden_size, n_layers, simplify=True, positional_encoding=False)
