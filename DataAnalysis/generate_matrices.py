import matplotlib.pyplot as plt
import numpy
from sklearn import metrics

actual = numpy.random.binomial(1,.9,size = 1000)
predicted = numpy.random.binomial(1,.9,size = 1000)

confusion_matrix = metrics.confusion_matrix(actual, predicted)

cm_display = metrics.ConfusionMatrixDisplay(confusion_matrix = confusion_matrix, display_labels = [False, True])

cm_display.plot()
plt.show()

def generate_confusion_matrix():
    '''
    This function will generate a confusion matrix for the specified dataset
    and save it in the same directory.
    '''


if __name__ == '__main__':
    datasets = []

    # For each dataset, generate a confusion matrix and save the image
    for dataset in datasets:
        generate_confusion_matrix()