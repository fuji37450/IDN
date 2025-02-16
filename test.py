from re import L
import torch
from dataset.dataset import SignatureLoader
from models.net import net
from utils import *
from sklearn import metrics
from tqdm import tqdm


def compute_pred_prob(predicted):
    predicted = (predicted[0] + predicted[1] + predicted[2]) / 3
    return predicted.view(-1)


def vote(predicted):
    for i in range(3):
        predicted[i][predicted[i] > 0.5] = 1
        predicted[i][predicted[i] <= 0.5] = 0
    predicted = predicted[0] + predicted[1] + predicted[2]

    predicted[predicted < 2] = 0
    predicted[predicted >= 2] = 1

    return predicted.view(-1)


def compute_accuracy(predicted, labels):
    predicted = vote(predicted)
    accuracy = torch.sum(predicted == labels).item() / labels.size()[0]
    return accuracy


def get_failed_pred_indices(predicted, labels):
    predicted = vote(predicted)
    return [i for i in range(len(predicted)) if predicted[i] != labels[i]]


if torch.cuda.is_available():
    device = 'cuda'
else:
    device = 'cpu'
print(device)

BATCH_SIZE = 32
args = parse_args()
test_set = SignatureLoader(root=args.dataset_dir, train=False)
test_loader = torch.utils.data.DataLoader(
    test_set, batch_size=2*BATCH_SIZE, shuffle=False)
assert args.model_dir != '', 'model_dir is required'

model = net().to(device)
model.load_state_dict(torch.load(args.model_dir))

predicted = []
labels = []
failed_pred_samples = []
with torch.no_grad():
    accuracys = []
    for inputs_, labels_ in tqdm(test_loader):
        labels_ = labels_.float()
        inputs_, labels_ = inputs_.to(device), labels_.to(device)
        predicted_ = model(inputs_)
        predicted += list(compute_pred_prob(predicted_).detach().cpu().numpy())
        labels += list(labels_.detach().cpu().numpy())
        accuracys.append(compute_accuracy(predicted_, labels_))
        failed_pred_indices = get_failed_pred_indices(predicted_, labels_)
        failed_pred_samples += [(inputs_[i].detach().cpu().numpy(),
                                 labels_[i].item()) for i in failed_pred_indices]
    accuracy_ = sum(accuracys) / len(accuracys)
print(f'test accuracy:{accuracy_:%}')

fpr, tpr, thresholds = metrics.roc_curve(labels, predicted)
auc = metrics.auc(fpr, tpr)
print(f'AUC: {auc}')
plot_roc_curve(auc, fpr, tpr, args.model_prefix)
plot_far_frr_curve(fpr=fpr, fnr=1-tpr, threshold=thresholds,
                   filename=args.model_prefix)
draw_failed_sample(failed_pred_samples)
