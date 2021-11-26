from src.model.model import make_model
from src.data.generator import Tokenizer, DataGenerator
from src.data.evaluation import ocr_metrics
import torch
import yaml
import cv2
import torchvision.transforms as T
import numpy as np
import src.data.preprocess as pp

device = "cuda:0" if torch.cuda.is_available() == True else "cpu"

with open("config.yaml", "r") as f:
    config = yaml.safe_load(f)


def single_image_inference(model, img, tokenizer, transform, device):
    """
    Run inference on single image
    """
    img = transform(img)
    imgs = img.unsqueeze(0).float().to(device)
    with torch.no_grad():
        memory = get_memory(model, imgs)
        out_indexes = [
            tokenizer.chars.index("SOS"),
        ]

        for i in range(128):
            mask = model.generate_square_subsequent_mask(i + 1).to(device)
            trg_tensor = torch.LongTensor(out_indexes).unsqueeze(1).to(device)
            output = model.vocab(
                model.transformer.decoder(
                    model.query_pos(model.decoder(trg_tensor)), memory, tgt_mask=mask
                )
            )
            out_token = output.argmax(2)[-1].item()
            if out_token == tokenizer.chars.index("EOS"):
                break

            out_indexes.append(out_token)

    pre = tokenizer.decode(out_indexes[1:])
    return pre


def get_memory(model, imgs):
    x = model.conv(model.get_feature(imgs))
    bs, _, H, W = x.shape
    pos = (
        torch.cat(
            [
                model.col_embed[:W].unsqueeze(0).repeat(H, 1, 1),
                model.row_embed[:H].unsqueeze(1).repeat(1, W, 1),
            ],
            dim=-1,
        )
        .flatten(0, 1)
        .unsqueeze(1)
    )
    return model.transformer.encoder(pos + 0.1 * x.flatten(2).permute(2, 0, 1))


if __name__ == "__main__":
    image_path = (
        "raw_data/trdg/image/abietinic_Saud_timekeepership_fraenum_normalization_6192.jpg"
    )
    img = pp.preprocess(image_path, input_size=(1024, 128, 1))

    # making image compatible with resnet
    img = np.repeat(img[..., np.newaxis], 3, -1)
    x_test = pp.normalization(img)

    charset = config["charset"]
    tokenizer = Tokenizer(charset)

    print("[INFO] Load pretrained model")
    model = make_model(hidden_dim=512, vocab_len=tokenizer.vocab_size)
    model.to(device)
    model.load_state_dict(
        torch.load("run/checkpoint_weights_eng_trdg.pt", map_location=device)
    )

    transform = T.Compose([T.ToTensor()])

    prediction = single_image_inference(model, x_test, tokenizer, transform, device)

    print("\n####################################")
    print("predicted text is: {}".format(prediction))
    cv2.imshow("Image ", cv2.imread(image_path))
    print("\n####################################")
    cv2.waitKey(0)
