from flask import Blueprint, request, abort
from scipy.stats import mode
import numpy as np
import joblib
import os

model = Blueprint("model", __name__, url_prefix="/api/model")


base_dir = os.path.abspath(os.path.dirname(__file__))

svm_model_path = os.path.join(base_dir, 'ML_model/saved_models/svm_model.pkl')
naive_bayes_model_path = os.path.join(base_dir, 'ML_model/saved_models/naive_bayes_model.pkl')
random_forest_model_path = os.path.join(base_dir, 'ML_model/saved_models/random_forest_model.pkl')
symptom_index_path = os.path.join(base_dir, 'ML_model/symptom_index.pkl')
data_dict_path = os.path.join(base_dir, 'ML_model/data_dict.pkl')

svm_model = joblib.load(svm_model_path)
naive_bayes_model = joblib.load(naive_bayes_model_path)
random_forest_model = joblib.load(random_forest_model_path)
symptom_index = joblib.load(symptom_index_path)
data_dict = joblib.load(data_dict_path)

@model.route('/predict', methods=["POST"])
def predict():
    symptoms = request.json.get('symptoms')
    
    if not symptoms:
        abort(400, "Symptoms not provided!")
        
    symptoms = symptoms.split(",") 
      
    input_data = [0] * len(data_dict["symptom_index"]) 
    for symptom in symptoms: 
        index = data_dict["symptom_index"][symptom] 
        input_data[index] = 1
           
    input_data = np.array(input_data).reshape(1,-1) 
       
    rf_prediction = data_dict["predictions_classes"][random_forest_model.predict(input_data)[0]] 
    nb_prediction = data_dict["predictions_classes"][naive_bayes_model.predict(input_data)[0]] 
    svm_prediction = data_dict["predictions_classes"][svm_model.predict(input_data)[0]] 
      
    final_prediction = mode([rf_prediction, nb_prediction, svm_prediction])[0][0] 
    predictions = { 
        "rf_model_prediction": rf_prediction, 
        "naive_bayes_prediction": nb_prediction, 
        "svm_model_prediction": svm_prediction, 
        "final_prediction":final_prediction 
    } 
    
    return predictions, 200
