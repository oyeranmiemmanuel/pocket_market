document.addEventListener('DOMContentLoaded', function(){

    const themeBtn = document.getElementById('theme-toggle');

    if(localStorage.getItem('theme') === 'dark'){
        document.body.classList.add('dark-mode');
    }

    if(themeBtn){

        themeBtn.addEventListener('click', function(){

            document.body.classList.toggle('dark-mode');

            if(document.body.classList.contains('dark-mode')){
                localStorage.setItem('theme', 'dark');
            }else{
                localStorage.setItem('theme', 'light');
            }

        });

    }

});
