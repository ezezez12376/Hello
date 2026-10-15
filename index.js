var msg=document.getElementById('msg');

document.getElementById('go').addEventListener('click',function(){

  var a=document.getElementById('n1').value.trim(),
  b=document.getElementById('n2').value.trim();

  if(!a||!b){msg.textContent='Nhập đủ tên hai người để bắt đầu nhé!';
    return;}

  msg.textContent='Sẵn sàng rồi, '+a+' và '+b+'! Phần câu hỏi sẽ có ở trang tiếp theo.';
});