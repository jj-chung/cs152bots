import matplotlib.pyplot as plt
import numpy as np
from sklearn import metrics

def generate_confusion_matrix(actual, predicted, save_name):
    '''
    This function will generate a confusion matrix for the specified dataset
    and save it in the same directory.
    Arguments:
        actual - List of actual labels (0s and 1s)
        predicted - List of predicted 
    '''
    confusion_matrix = metrics.confusion_matrix(actual, predicted)
    cm_display = metrics.ConfusionMatrixDisplay(confusion_matrix = confusion_matrix, display_labels = ["Toxic", "Non-toxic"])

    cm_display.plot()
    plt.show()
    plt.savefig(save_name)

if __name__ == '__main__':
    datasets = []

    # For each dataset, generate a confusion matrix and save the image
    for dataset in datasets:
        generate_confusion_matrix(actual, predicted, save_name)